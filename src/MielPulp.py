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
        self.boundsLabels = list(bounds.columns)[1::] # no tengo en cuenta la primera
        #cotas de las propiedades
        self.boundMin = dict(zip(self.boundsLabels, bounds.loc[0,"Kilos"::]))
        self.boundMax = dict(zip(self.boundsLabels, bounds.loc[1,"Kilos"::]))
    
    switcherBounds = {
            "excel" : setBoundsFromExcel
            }

    def setBoundsFromDir(self, dirBounds, typeFile):
        func = self.switcherBounds.get(typeFile, self.defaultCase)
        return func(self, dirBounds)


    def getDataJson(self):
        return self.data.to_json()
    
    def addResult(self, x, y):
        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)
        l = [x[j].varValue for j in LOTES]
        m = [[int(y[l][m].varValue) for l in LOTES] for m in MUESTRAS]
        self.results.append((l, m))

    def processModel(self, dirSolver = ""):

        #obtengo la cantidad posible de lotes, sumando todos los pesos y lo divido por la cota minima
        self.cntLotes = int(sum(self.data["Kilos"])/self.boundMin["Kilos"])
        self.cntMuestras = self.data.shape[0]
 
        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)

        #----------------------------------------------------------------------------------
        #lo siguiente define todo el modelo, variables y restricciones 
        #variable de lotes a armar
        x = pulp.LpVariable.dicts("X", LOTES, cat = "Binary")
        #matriz binaria
        y = pulp.LpVariable.dicts("Y", (LOTES, MUESTRAS), cat = "Binary")
        
        #modelo
        model = pulp.LpProblem("Miel_Combinacion", pulp.LpMaximize)
        
    
        model += pulp.lpSum(
            [x[l] for l in LOTES]
            + [y[l][m] for l in LOTES for m in MUESTRAS]
        )  
        
        #restricción para que el modelo comience por el primer lote    
        for l in LOTES[0:self.cntLotes-1]:
            model += x[l] >= x[l+1]
        
        for l in LOTES:
            #restriccion de correlacion entre variable binarias
            for m in MUESTRAS:
                model += x[l] >= y[l][m]
        
    
        #Restriccion de que cada muestra pertenezca a un lote o a ninguno
        for m in MUESTRAS:
            model += pulp.lpSum([y[l][m] for l in LOTES] ) <= 1
        
        for l in LOTES:
                kilos = sum([self.data["Kilos"][m] * y[l][m] for m in MUESTRAS])
                model += kilos >= self.boundMin["Kilos"] * x[l], "Restricción kilos cota inferior lote"+str(l)
                model += kilos <= self.boundMax["Kilos"] * x[l], "Restricción kilos cota superior lote"+str(l)
                for p in self.boundsLabels[1::]:#a partir de 1 para no incluir kilos
                    valueBound= sum([self.data[p][m] * y[l][m] * self.data["Kilos"][m] for m in MUESTRAS])
                    #no se puede dividir por lo tanto paso kilos del lota como multiplicación del otro lado
                    model += valueBound >= self.boundMin[p] * kilos, "Restricción propiedad " + p + " cota inferior lote"+str(l) 
                    model += valueBound <= self.boundMax[p] * kilos, "Restricción propiedad " + p + " cota superior lote"+str(l)
    
        self.results = []
        solver = None
        if dirSolver != "":
            solver = pulp.COIN_CMD(path=dirSolver, threads=1, mip=1, options=['sec','500'], fracGap=0.1, msg=1)
            model.solve(solver)
        else:
            model.solve()


        accumOptimal = 0

        if  pulp.LpStatus[model.status] == "Optimal":
            opt = pulp.value(model.objective)
            accumOptimal += 1
            self.addResult(x, y)
            while True:
                model += pulp.lpSum([y[l][m] for l in LOTES for m in MUESTRAS if y[l][m] >= 0.99] ) <= sum( [y[l][m].varValue for l in LOTES for m in MUESTRAS]) - 1
                
                if dirSolver != "":
                    model.solve(solver)
                else:
                    model.solve() 


                if pulp.value(model.objective) >= opt - 1e-6:
                    accumOptimal += 1
                    self.results.append((x,y))
                else:
                    break
    
        return accumOptimal

    def getResults(self):
        return self.results
 
    def saveResultsToExcelDir(self, dirToSave):
    
        LOTES = range(0, self.cntLotes)
        MUESTRAS = range(0, self.cntMuestras)
    
        rowLabelsMuestras = self.data["Muestra"]
        colLabelsMuestras = ["Lote " + str(num) for num in range(1, self.cntLotes+1)]
        rowLabelsLotes = colLabelsMuestras 
        colLabelsLotes = self.boundsLabels
        cntParametros = len(self.boundsLabels)
        matrizLoVal = np.zeros((self.cntLotes, cntParametros))

        write = pd.ExcelWriter(dirToSave)

        for i in range(len(self.results)):
            (x, y) = self.results[i]
            matriz = dict(zip(rowLabelsMuestras, y))
            matrizMuLo = pd.DataFrame.from_dict(matriz, orient = "index", columns = colLabelsMuestras)

            for il,l in enumerate(LOTES):
                if x[l]:
                    kilosLote = sum([y[m][l] * self.data["Kilos"][m] for m in MUESTRAS])
                    matrizLoVal[il,0] = kilosLote
                    for ip, p in enumerate(self.boundsLabels[1::]):#a partir de 1 para no incluir kilos
                        valorProp = sum([self.data[p][m] * y[m][l] * self.data["Kilos"][m] for m in MUESTRAS])/kilosLote
                        matrizLoVal[il,ip + 1] = valorProp
                    
            matrizLoVal = dict(zip(rowLabelsLotes, np.round(matrizLoVal, 4)))
            matrizLoVal = pd.DataFrame.from_dict(matrizLoVal, orient = "index", columns = colLabelsLotes)
    
            matrizMuLo.to_excel(write, sheet_name = "MuestrasLotes_" + str(i+1))
            matrizLoVal.to_excel(write, sheet_name = "LotesValores_" + str(i+1))
            write.save()
    




#miel = MielPulp()
#miel.setDataFromDir("../archivos/DatosMuestras 200721.xlsx", "excel")
#miel.setBoundsFromDir("../cotasPropiedades.xlsx", "excel")
#miel.processModel()
#miel.saveResultsToExcelDir("resultados.xlsx")
