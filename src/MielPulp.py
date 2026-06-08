import numpy as np
import pandas as pd
import pulp

Z_99 = 2.5758293035489


class MielPulp:

    # ------------------------------------------------------------------ carga

    def setDataFromExcel(self, dirData):
        self.data = pd.read_excel(dirData).reset_index(drop=True)

    switcherData = {"excel": setDataFromExcel}

    def defaultCase(self, dirData):
        print("Invalid type file")

    def setDataFromDir(self, dirData, typeFile):
        func = self.switcherData.get(typeFile, self.defaultCase)
        return func(self, dirData)

    def setBoundsFromExcel(self, dirBounds):
        xl = pd.ExcelFile(dirBounds)
        self.tipos = {}
        for sheet in xl.sheet_names:
            df = pd.read_excel(dirBounds, sheet_name=sheet)
            labels = list(df.columns)[1:]
            bound_min = dict(zip(labels, [df.loc[0, c] for c in labels]))
            bound_max = dict(zip(labels, [df.loc[1, c] for c in labels]))
            self.tipos[sheet] = {"min": bound_min, "max": bound_max, "labels": labels}

    switcherBounds = {"excel": setBoundsFromExcel}

    def setBoundsFromDir(self, dirBounds, typeFile):
        func = self.switcherBounds.get(typeFile, self.defaultCase)
        return func(self, dirBounds)

    def getDataJson(self):
        return self.data.to_json()

    # --------------------------------------------------------------- helpers

    def _positionColumn(self):
        for name in ["Columnas", "Columna", "Fila"]:
            if name in self.data.columns:
                return name
        return None

    def _parseColumnas(self, valor):
        return set(str(valor).replace(" ", "").split(","))

    def _colorColumn(self):
        for name in ["Color", "P1"]:
            if name in self.data.columns:
                return name
        return None

    # ------------------------------------------- pre-proceso antes del modelo

    def _prefilter(self):
        """Para cada tambor, determina a qué tipos podría pertenecer."""
        M = range(len(self.data))
        self.eligible = {m: set() for m in M}
        color_col = self._colorColumn()

        for tipo, bounds in self.tipos.items():
            for m in M:
                ok = True
                for p in bounds["labels"][1:]:   # saltear Kilos
                    if p == color_col:            # Color se verifica por IC, no por media
                        continue
                    if p not in self.data.columns:
                        continue
                    val = float(self.data[p].iloc[m])
                    if val < bounds["min"][p] or val > bounds["max"][p]:
                        ok = False
                        break
                if ok:
                    self.eligible[m].add(tipo)

    def _margenColorLP(self):
        """Calcula el margen de seguridad del IC para la restricción de Color en el LP."""
        color_col = self._colorColumn()
        if color_col is None or color_col not in self.data.columns:
            return {}

        sigma = float(np.sqrt(
            np.sum((self.data[color_col].values - np.mean(self.data[color_col].values)) ** 2)
            / len(self.data)
        ))

        margenes = {}
        for tipo, bounds in self.tipos.items():
            if color_col not in bounds["labels"]:
                continue
            max_kilos_barrel = float(self.data["Kilos"].max())
            n_min = max(1, int(bounds["min"]["Kilos"] / max_kilos_barrel))
            margen = Z_99 * sigma / np.sqrt(n_min)
            margenes[tipo] = {
                "effective_max": bounds["max"][color_col] - margen,
                "bound_min": bounds["min"][color_col],
            }
        return margenes

    # ---------------------------------------------------- cálculo IC por lote

    def _colorIC(self, batch):
        """IC superior 99% de Color para los tambores del lote."""
        color_col = self._colorColumn()
        if color_col is None or not batch:
            return None
        vals = [float(self.data[color_col].iloc[m]) for m in batch]
        n = len(vals)
        media = sum(vals) / n
        desvio = np.sqrt(sum((v - media) ** 2 for v in vals) / n)
        return media + Z_99 * (desvio / np.sqrt(n))

    # ------------------------------------------------------------ optimización

    def processModel(self, dirSolver="", timeLimit=7200):
        M = list(range(len(self.data)))

        self._prefilter()
        color_col = self._colorColumn()
        margenes_color = self._margenColorLP()

        total_kilos = float(self.data["Kilos"].sum())
        global_min_kilos = min(b["min"]["Kilos"] for b in self.tipos.values())
        total_slots_max = int(total_kilos / global_min_kilos)

        # slots por tipo
        tipo_slots = {}
        for tipo, bounds in self.tipos.items():
            elig_kilos = sum(
                float(self.data["Kilos"].iloc[m]) for m in M if tipo in self.eligible[m]
            )
            n_slots = min(int(elig_kilos / bounds["min"]["Kilos"]), total_slots_max)
            tipo_slots[tipo] = list(range(max(n_slots, 0)))

        # variables
        x, y = {}, {}
        for tipo, slots in tipo_slots.items():
            safe = tipo.replace(" ", "_").replace("/", "_")
            x[tipo] = pulp.LpVariable.dicts(f"X_{safe}", slots, cat="Binary")
            y[tipo] = {}
            elig_m = [m for m in M if tipo in self.eligible[m]]
            for l in slots:
                y[tipo][l] = pulp.LpVariable.dicts(f"Y_{safe}_{l}", elig_m, cat="Binary")

        model = pulp.LpProblem("Miel_MultiTipo", pulp.LpMaximize)

        # objetivo: maximizar kilos asignados
        model += pulp.lpSum(
            float(self.data["Kilos"].iloc[m]) * y[tipo][l][m]
            for tipo, slots in tipo_slots.items()
            for l in slots
            for m in y[tipo][l]
        )

        # orden de slots (sin huecos)
        for tipo, slots in tipo_slots.items():
            for i in range(len(slots) - 1):
                model += x[tipo][slots[i]] >= x[tipo][slots[i + 1]]

        # correlación: si hay tambor en lote, lote está activo
        for tipo, slots in tipo_slots.items():
            for l in slots:
                for m in y[tipo][l]:
                    model += x[tipo][l] >= y[tipo][l][m]

        # cada tambor en a lo sumo un lote (de cualquier tipo)
        for m in M:
            asignado = [
                y[tipo][l][m]
                for tipo, slots in tipo_slots.items()
                for l in slots
                if m in y[tipo][l]
            ]
            if asignado:
                model += pulp.lpSum(asignado) <= 1

        # restricciones de kilos y propiedades por tipo-slot
        for tipo, bounds in self.tipos.items():
            mc = margenes_color.get(tipo)
            for l in tipo_slots[tipo]:
                elig_m = list(y[tipo][l].keys())
                if not elig_m:
                    model += x[tipo][l] == 0
                    continue

                kilos_l = pulp.lpSum(float(self.data["Kilos"].iloc[m]) * y[tipo][l][m] for m in elig_m)
                model += kilos_l >= bounds["min"]["Kilos"] * x[tipo][l]
                model += kilos_l <= bounds["max"]["Kilos"] * x[tipo][l]

                n_batch = pulp.lpSum(y[tipo][l][m] for m in elig_m)

                for p in bounds["labels"][1:]:
                    if p not in self.data.columns:
                        continue

                    if p == color_col and mc is not None:
                        # restricción IC: media simple <= effective_max
                        color_sum = pulp.lpSum(float(self.data[p].iloc[m]) * y[tipo][l][m] for m in elig_m)
                        model += color_sum <= mc["effective_max"] * n_batch
                        model += color_sum >= mc["bound_min"] * n_batch
                    else:
                        # restricción estándar: media ponderada por kilos
                        val_p = pulp.lpSum(
                            float(self.data[p].iloc[m]) * float(self.data["Kilos"].iloc[m]) * y[tipo][l][m]
                            for m in elig_m
                        )
                        model += val_p >= bounds["min"][p] * kilos_l
                        model += val_p <= bounds["max"][p] * kilos_l

        # solver: HiGHS primero, luego CBC externo, luego CBC bundled
        self.gap = None
        solved = False
        for attempt in range(3):
            try:
                if attempt == 0:
                    solver = pulp.HiGHS_CMD(msg=True, timeLimit=timeLimit, gapRel=0.005)
                elif attempt == 1 and dirSolver:
                    solver = pulp.COIN_CMD(path=dirSolver, msg=True, options=["sec", str(timeLimit)])
                else:
                    solver = pulp.PULP_CBC_CMD(msg=True, timeLimit=timeLimit)
                model.solve(solver)
                solved = True
                break
            except Exception:
                continue

        # extraer resultados
        self.results = {}
        if pulp.value(model.objective) is not None:
            for tipo, slots in tipo_slots.items():
                lotes = []
                for l in slots:
                    if x[tipo][l].varValue and x[tipo][l].varValue > 0.5:
                        batch = [
                            m for m in y[tipo][l]
                            if y[tipo][l][m].varValue and y[tipo][l][m].varValue > 0.5
                        ]
                        if batch:
                            lotes.append(batch)
                if lotes:
                    self.results[tipo] = lotes

        # ordenar por posición (menos movimiento primero)
        pos_col = self._positionColumn()
        if pos_col:
            def score(res):
                bonus = 0
                for lotes in res.values():
                    for batch in lotes:
                        all_cols = []
                        for m in batch:
                            all_cols.extend(self._parseColumnas(self.data[pos_col].iloc[m]))
                        bonus += len(all_cols) - len(set(all_cols))
                return bonus
            # resultado único, pero guardamos el score para mostrarlo
            self.rowScore = score(self.results)
        else:
            self.rowScore = 0

        return len(self.results)

    def getResults(self):
        return self.results

    # ----------------------------------------------------------------- output

    def saveResultsToExcelDir(self, dirToSave):
        if not self.results:
            return

        pos_col = self._positionColumn()
        color_col = self._colorColumn()
        writer = pd.ExcelWriter(dirToSave)

        for tipo, lotes in self.results.items():
            bounds = self.tipos[tipo]
            rows_asig, rows_val = [], []

            for i, batch in enumerate(lotes):
                kilos_lote = sum(float(self.data["Kilos"].iloc[m]) for m in batch)
                nombres = [str(self.data["Muestra"].iloc[m]) for m in batch]

                row_asig = {"Lote": i + 1, "Tambores": ", ".join(nombres), "Kilos": round(kilos_lote, 1)}
                if pos_col:
                    cols_lote = set().union(*[self._parseColumnas(self.data[pos_col].iloc[m]) for m in batch])
                    row_asig["Columnas"] = ", ".join(sorted(cols_lote))
                rows_asig.append(row_asig)

                row_val = {"Lote": i + 1, "Kilos": round(kilos_lote, 1)}
                for p in bounds["labels"][1:]:
                    if p not in self.data.columns:
                        continue
                    if p == color_col:
                        # mostrar IC superior 99%
                        ic = self._colorIC(batch)
                        row_val[f"{p} (IC sup 99%)"] = round(ic, 4) if ic is not None else ""
                    else:
                        val = sum(
                            float(self.data[p].iloc[m]) * float(self.data["Kilos"].iloc[m])
                            for m in batch
                        ) / kilos_lote
                        row_val[p] = round(val, 4)

                if pos_col:
                    cols_used = len(set().union(*[self._parseColumnas(self.data[pos_col].iloc[m]) for m in batch]))
                    row_val["Columnas utilizadas"] = cols_used

                rows_val.append(row_val)

            base = tipo[:14]
            pd.DataFrame(rows_asig).to_excel(writer, sheet_name=f"{base}_Asignacion", index=False)
            pd.DataFrame(rows_val).to_excel(writer, sheet_name=f"{base}_Valores", index=False)

        writer.close()
