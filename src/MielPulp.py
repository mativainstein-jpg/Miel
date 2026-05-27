import numpy as np
import pandas as pd
import pulp

class MielPulp:

    def setDataFromExcel(self, dirData):
        self.data = pd.read_excel(dirData)

    switcherData = {
            "excel" : setDataFromExcel
            }

    def defaultCase(self, dirData):
        print("Invalid type file")

    def setDataFromDir(self, dirData, typeFile):
        func = self.switcherData.get(typeFile, self.defaultCase)
        return func(self, dirData)

    def setBoundsFromExcel(self, dirBounds):
        bounds = pd.read_excel(dirBounds)
        self.setBounds(bounds)

    def setBounds(self, bounds):
        self.boundsLabels = list(bounds.columns)[1::]  # no tengo en cuenta la primera
        self.boundMin = dict(zip(self.boundsLabels, bounds.loc[0, "Kilos"::]))
        self.boundMax = dict(zip(self.boundsLabels, bounds.loc[1, "Kilos"::]))

    switcherBounds = {
            "excel" : setBoundsFromExcel
            }

    def setBoundsFromDir(self, dirBounds, typeFile):
        func = self.switcherBounds.get(typeFile, self.defaultCase)
        return func(self, dirBounds)

    def getDataJson(self):
        return self.data.to_json()

    def _positionColumn(self):
        """Devuelve el nombre de la columna de posición si existe, o None."""
        for name in ["Columna", "Fila"]:
            if name in self.data.columns:
                return name
        return None

    def computeRowScore(self, x_vals, y_vals):
        """Calcula cuántos tambores comparten columna con otro en el mismo lote.
        Mayor puntaje = menos movimiento = mejor solución de posición."""
        col = self._positionColumn()
        if col is None:
            return 0
        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)
        posiciones = list(self.data[col])
        bonus = 0
        for l in LOTES:
            if x_vals[l]:
                samples_in_batch = [m for m in MUESTRAS if y_vals[m][l]]
                if samples_in_batch:
                    cols_used = len(set(posiciones[m] for m in samples_in_batch))
                    # tambores en lote menos columnas distintas = ahorro de movimiento
                    bonus += len(samples_in_batch) - cols_used
        return bonus

    def addResult(self, x, y):
        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)
        x_vals = [x[j].varValue for j in LOTES]
        # y_vals[m][l] = 1 si la muestra m está en el lote l
        y_vals = [[int(y[l][m].varValue) for l in LOTES] for m in MUESTRAS]
        self.results.append((x_vals, y_vals))

    def processModel(self, dirSolver=""):

        # cantidad posible de lotes: suma de kilos / cota mínima
        self.cntLotes = int(sum(self.data["Kilos"]) / self.boundMin["Kilos"])
        self.cntMuestras = self.data.shape[0]

        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)

        # variables de decisión
        x = pulp.LpVariable.dicts("X", LOTES, cat="Binary")
        y = pulp.LpVariable.dicts("Y", (LOTES, MUESTRAS), cat="Binary")

        model = pulp.LpProblem("Miel_Combinacion", pulp.LpMaximize)

        model += pulp.lpSum(
            [x[l] for l in LOTES]
            + [y[l][m] for l in LOTES for m in MUESTRAS]
        )

        # el modelo comienza por el primer lote
        for l in LOTES[0:self.cntLotes - 1]:
            model += x[l] >= x[l + 1]

        for l in LOTES:
            for m in MUESTRAS:
                model += x[l] >= y[l][m]

        # cada muestra pertenece a un lote o a ninguno
        for m in MUESTRAS:
            model += pulp.lpSum([y[l][m] for l in LOTES]) <= 1

        for l in LOTES:
            kilos = sum([self.data["Kilos"][m] * y[l][m] for m in MUESTRAS])
            model += kilos >= self.boundMin["Kilos"] * x[l], "Restricción kilos cota inferior lote" + str(l)
            model += kilos <= self.boundMax["Kilos"] * x[l], "Restricción kilos cota superior lote" + str(l)
            for p in self.boundsLabels[1::]:
                valueBound = sum([self.data[p][m] * y[l][m] * self.data["Kilos"][m] for m in MUESTRAS])
                model += valueBound >= self.boundMin[p] * kilos, "Restricción propiedad " + p + " cota inferior lote" + str(l)
                model += valueBound <= self.boundMax[p] * kilos, "Restricción propiedad " + p + " cota superior lote" + str(l)

        self.results = []
        solver = None
        if dirSolver != "":
            solver = pulp.COIN_CMD(path=dirSolver, threads=1, mip=1, options=['sec', '500'], fracGap=0.1, msg=1)
            model.solve(solver)
        else:
            model.solve()

        accumOptimal = 0

        if pulp.LpStatus[model.status] == "Optimal":
            opt = pulp.value(model.objective)
            accumOptimal += 1
            self.addResult(x, y)
            while True:
                model += pulp.lpSum(
                    [y[l][m] for l in LOTES for m in MUESTRAS if y[l][m] >= 0.99]
                ) <= sum([y[l][m].varValue for l in LOTES for m in MUESTRAS]) - 1

                if dirSolver != "":
                    model.solve(solver)
                else:
                    model.solve()

                if pulp.value(model.objective) >= opt - 1e-6:
                    accumOptimal += 1
                    self.addResult(x, y)
                else:
                    break

        # Si hay columna de posición, ordenar soluciones por menor movimiento
        if self._positionColumn() is not None and self.results:
            self.results.sort(key=lambda r: -self.computeRowScore(r[0], r[1]))

        self.rowScores = [self.computeRowScore(r[0], r[1]) for r in self.results]

        return accumOptimal

    def getResults(self):
        return self.results

    def saveResultsToExcelDir(self, dirToSave):

        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)

        rowLabelsMuestras = self.data["Muestra"]
        colLabelsMuestras = ["Lote " + str(num) for num in range(1, self.cntLotes + 1)]
        rowLabelsLotes = colLabelsMuestras

        pos_col = self._positionColumn()

        # columnas para LotesValores: propiedades + columnas utilizadas si corresponde
        colLabelsLotes = self.boundsLabels + (["Columnas utilizadas"] if pos_col else [])
        cntParametros = len(colLabelsLotes)

        write = pd.ExcelWriter(dirToSave)

        for i in range(len(self.results)):
            (x, y) = self.results[i]

            matrizLoVal = np.zeros((self.cntLotes, cntParametros))

            # matriz de muestras vs lotes (con columna de posición si existe)
            muestra_data = {}
            for im, muestra_name in enumerate(rowLabelsMuestras):
                row_data = [y[im][l] for l in LOTES]
                if pos_col:
                    row_data.append(self.data[pos_col].iloc[im])
                muestra_data[muestra_name] = row_data

            col_labels_mu = colLabelsMuestras + ([pos_col] if pos_col else [])
            matrizMuLo = pd.DataFrame.from_dict(muestra_data, orient="index", columns=col_labels_mu)

            for il, l in enumerate(LOTES):
                if x[l]:
                    kilosLote = sum([y[m][l] * self.data["Kilos"][m] for m in MUESTRAS])
                    matrizLoVal[il, 0] = kilosLote
                    for ip, p in enumerate(self.boundsLabels[1::]):
                        valorProp = sum([self.data[p][m] * y[m][l] * self.data["Kilos"][m] for m in MUESTRAS]) / kilosLote
                        matrizLoVal[il, ip + 1] = valorProp
                    if pos_col:
                        samples_in_batch = [m for m in MUESTRAS if y[m][l]]
                        cols_used = len(set(self.data[pos_col].iloc[m] for m in samples_in_batch))
                        matrizLoVal[il, len(self.boundsLabels)] = cols_used

            matrizLoVal_dict = dict(zip(rowLabelsLotes, np.round(matrizLoVal, 4)))
            matrizLoVal_df = pd.DataFrame.from_dict(matrizLoVal_dict, orient="index", columns=colLabelsLotes)

            matrizMuLo.to_excel(write, sheet_name="MuestrasLotes_" + str(i + 1))
            matrizLoVal_df.to_excel(write, sheet_name="LotesValores_" + str(i + 1))

        write.close()
