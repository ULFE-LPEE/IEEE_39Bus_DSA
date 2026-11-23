'''
Author: Matjaz Skrlec
date: 03. 10. 2024
version: 1.0
description: This module is used for handling files during Dynamic security assessment.
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import os.path
import math
import pandas as pd
import DSA.STATIC as STATIC
import PFSupport.GetElements as GetElements
import logging
import pickle
import shutil
from pathlib import Path
from collections.abc import Iterable
from typing import Literal, List, TextIO
type Mode = Literal['ceil', 'floor', 'round']
import numbers

def ExtractForName(ForName: str):
    forIndex = ForName.find(":")
    if forIndex:
        ForName = ForName[forIndex+1:]
    return ForName

def CheckIfCsvEmpty(filepath) -> bool:
    if os.path.exists(filepath):
        df = pd.read_csv(filepath)
        if df.empty:
            print(f' file {filepath} is empty.')
            return True
        else:
            return False
    else:
        print(f' file {filepath} doesn\'t exist.')
        return True

def count_csv_rows(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return sum(1 for _ in f) - 1  # Subtract 1 if there's a header

def strToFloat(string: str) -> float:
    return(float(string.replace(",",".")))

def floatToStr(floater: float, dec: int = 2, rounding: Mode = 'round') -> str:
    assert(rounding in ['ceil', 'floor', 'round']), "Invalid entry of argument 'rounding'. Only 'ceil', 'fllor' and 'round' are acceotable."
    correctionNumb = 10**dec
    if rounding == 'round':
        return(str(round(floater*correctionNumb)/correctionNumb).replace(".",","))
    elif rounding == 'ceil':
        return(str(math.ceil(floater*correctionNumb)/correctionNumb).replace(".",","))
    elif rounding == 'floor':
        return(str(math.floor(floater*correctionNumb)/correctionNumb).replace(".",","))

def writeIterable(file: TextIO, Iter: Iterable):
    for i, val in enumerate(Iter):
        if i == 0:
            if isinstance(val, Iterable) and type(val) != str:
                file.write("(")
                writeIterable(file, val)
            else:
                file.write("(%s" % val)
        else:
            if isinstance(val, Iterable) and type(val) != str:
                file.write(",")
                writeIterable(file, val)
            else:
                file.write(",%s" % val)
    file.write(")")

def returnAfterChar(string: str, char: str) -> str:
    revStr = string[::-1]
    charCount = 0
    for character in revStr:
        if character == char:
            break
        else:
            charCount += 1
    return(revStr[:charCount][::-1])

def replaceWeirdChars(string: str) -> str:
    string.encode('utf-8').decode('utf-8')
    string.replace("Ž","Z")
    string.replace("Š","S")
    string.replace("Č","C")
    string.replace("©","C")
    string.replace("®","C")
    return(string)

def saveResultsToTemporaryFileTSA(results: List, fileName: str, ) -> str:
    tempDir = os.path.join(os.getcwd(), "temp_results")
    os.makedirs(tempDir, exist_ok=True)
    file_indexing = 0
    tempFile = os.path.join(tempDir, f"{fileName}_{file_indexing}.pkl")
    while os.path.exists(tempFile):
        file_indexing = file_indexing + 1
        tempFile = os.path.join(tempDir, f"{fileName}_{file_indexing}.pkl")

    with open(tempFile, "wb") as f:
        pickle.dump(results, f)
    
    return tempFile

def saveResultsToTemporaryFileFSA(results: List, fileName: str, ) -> str:
    tempDir = os.path.join(os.getcwd(), "temp_results")
    os.makedirs(tempDir, exist_ok=True)
    tempFile = os.path.join(tempDir, f"{fileName}.pkl")
    file_indexing = 0
    tempFile = os.path.join(tempDir, f"{fileName}_{file_indexing}.pkl")
    while os.path.exists(tempFile):
        file_indexing = file_indexing + 1
        tempFile = os.path.join(tempDir, f"{fileName}_{file_indexing}.pkl")

    with open(tempFile, "wb") as f:
        pickle.dump(results, f)
    
    return tempFile

def loadResultsFromTemporaryFile(tempFilePath: str) -> List:
    with open(tempFilePath, "rb") as f:
        Info = pickle.load(f)

    return Info

def concat_and_prune(import_file: str, align_file: str, EV_aligned_pruned_file: str, min_mag: int | float):
    '''
    This function creates a readable file from an alligned eigenvalue and an alligned eigenvalue/eigenvector file from a model analysis file powerfactory creates.
    '''

    assert(type(import_file) == str), "Argument 'import_file' is not of type str"
    assert(type(align_file) == str), "Argument 'align_file' is not of type str"
    assert(type(EV_aligned_pruned_file) == str), "Argument 'Ev_aligned_priden_file' is not of type str"
    assert(type(min_mag) in [int, float]), "Argument 'min mag' is not of type int or float"

    #put all modes in same row
    file1 = open(import_file, 'r',encoding = "utf-8")
    file2 = open(align_file, 'w+', encoding = "utf-8")
    file2.truncate()
    Lines = file1.readlines()

    n_modes = len(Lines)-1

    count = 0
    for line in Lines:
        if count == 0 or count == 1:
            line = line.rstrip("\n")
            write_str = ""
            for i in range(n_modes-1):
                if i != n_modes-2:
                    write_str = write_str + line + ";"
                else:
                    write_str = write_str + line + "\n"
            file2.write(write_str)
        elif count != n_modes:
            file2.write(line.rstrip("\n")+";")
        else: 
            file2.write(line)
        count = count+1

    file1.close()
    file2.close()

    #remove magnitudes less than prescribed
    aligned_db = pd.read_csv(align_file, sep = ";", encoding = "utf-8", low_memory=False)
    raw_db = pd.read_csv(import_file, sep = ";", encoding = "utf-8", low_memory=False)
    info_len = raw_db.shape[1]

    curr_mode = 1
    offset = curr_mode-1
    curr_coll_n = 0

    cols_to_remove = []

    for column in aligned_db.columns:
        #check if new mode
        if curr_coll_n == info_len:
            offset = offset +1
            curr_coll_n = 0
        #check if 1st 3 cols of new mode    
        if curr_coll_n < 3:
            curr_coll_n = curr_coll_n +1
            continue
        else:
            #check if mag or phase
            if (curr_coll_n % 2) == 1:
                #check if mag less than min_mag
                if float(str(aligned_db[column][1]).replace(",",".")) < min_mag:
                    cols_to_remove.append(column)
                    cols_to_remove.append(aligned_db.iloc[:,aligned_db.columns.get_indexer([column])+1].columns[0])

        curr_coll_n = curr_coll_n +1

    pruned_aligned_db = aligned_db.drop(columns = cols_to_remove)
    pruned_aligned_db.to_csv(EV_aligned_pruned_file,sep = ";")

def CheckForSameRows(main_LF: str, main_TSA: str, main_SSSA: str, main_FSA: str):
    '''
    This function checks if all saved databases have the same amount of entrys
    '''
    assert(type(main_LF) == str), "Argument 'main_LF' is not od type str"
    assert(type(main_TSA) == str), "Argument 'main_LF' is not od type str"
    assert(type(main_SSSA) == str), "Argument 'main_LF' is not od type str"
    assert(type(main_FSA) == str), "Argument 'main_LF' is not od type str"

    main_LF_exists = 1
    main_TSA_exists = 1
    main_SSSA_exists = 1
    main_FSA_exists = 1

    if not os.path.isfile(main_LF):
        print("File given with Argument 'main_LF' doesn't exist")
        logging.warning("File given with Argument 'main_LF' doesn't exist")
        main_LF_exists = 0
    if not os.path.isfile(main_TSA):
        print("File given with Argument 'main_TSA' doesn't exist")
        logging.warning("File given with Argument 'main_TSA' doesn't exist")
        main_TSA_exists = 0
    if not os.path.isfile(main_SSSA):
        print("File given with Argument 'main_SSSA' doesn't exist")
        logging.warning("File given with Argument 'main_SSSA' doesn't exist")
        main_SSSA_exists = 0
    if not os.path.isfile(main_FSA):
        print("File given with Argument 'main_FSA' doesn't exist")
        logging.warning("File given with Argument 'main_FSA' doesn't exist")
        main_FSA_exists = 0

    if (main_LF_exists == main_TSA_exists) and (main_LF_exists == main_SSSA_exists) and (main_LF_exists == main_FSA_exists):
        if (main_LF_exists == 0):
            return(True)
    else:
        print("some main files exist and some don't. Make sure all main files either exist or there are no files in the main files folder")
        logging.error("some main files exist and some don't. Make sure all main files either exist or there are no files in the main files folder")
        return(False)

    LF_len = count_csv_rows(main_LF)
    TSA_len = count_csv_rows(main_TSA)
    SSSA_len = count_csv_rows(main_SSSA)
    FSA_len = count_csv_rows(main_FSA)

    if LF_len != TSA_len:
        print("Lodaflow database is not the same length as TSA database")
        logging.error("Lodaflow database is not the same length as TSA database")
        return(False)
    if LF_len != SSSA_len:
        print("Loadflow database is not the same length as SSSA database")
        logging.error("Loadflow database is not the same length as SSSA database")
        return(False)
    if LF_len != FSA_len:
        print("Loadflow database is not the same length as FSA database")
        logging.error("Loadflow database is not the same length as FSA database")
        return(False)

    return(True)

def DeleteTempCsv(file_name: str):
    '''
    This function deletes a file.
    '''
    assert(type(file_name) == str), "Argument 'file_name' is not string."

    os.remove(file_name)

def AppendTempCsvToMainCsv(tempCsv_file_name: str, mainCsv_file_name: str):
    '''
    This function appends a temporary csv entry file to a main csv file.
    '''
    assert(type(tempCsv_file_name) == str ), "Argument 'tempCsv_file_name' isn't of type string"
    assert(type(mainCsv_file_name) == str), "Argument 'mainCsv_file_name' isn't of type string"

    if os.path.isfile(mainCsv_file_name):
        Df_main = pd.read_csv(mainCsv_file_name, sep = ";",index_col = 0, encoding = "utf-8", low_memory=False)
        Df_temp = pd.read_csv(tempCsv_file_name, sep = ";", encoding = "utf-8", index_col = False, low_memory=False)
        new_main = pd.concat([Df_main, Df_temp], ignore_index=True)
        new_main.to_csv(mainCsv_file_name,sep = ";")

    else:   
        Df_temp = pd.read_csv(tempCsv_file_name, sep = ";", encoding = "utf-8", index_col = False, low_memory=False)
        Df_temp.to_csv(mainCsv_file_name, sep = ";", index = True, encoding = "utf-8")

def MoveTempCsvToMainDir(tempCsv_file_name: str, mainCsv_file_dir: str, mainCsv_file_name: str):
    '''
    This function copys a temporary csv file to the main file directory, and changes its name to a desired name. 
    '''
    assert(type(tempCsv_file_name) == str ), "Argument 'tempCsv_file_name' isn't of type string"
    assert(type(mainCsv_file_dir) == str ), "Argument 'mainCsv_file_dir' isn't of type string"
    assert(type(mainCsv_file_name) == str ), "Argument 'mainCsv_file_name' isn't of type string"

    ID_number = 1
    main_csv_file_full_path = mainCsv_file_dir+"\\"+mainCsv_file_name
    main_csv_file_name_parts = mainCsv_file_name.split(".")

    source = Path(tempCsv_file_name)
    destination = Path(main_csv_file_full_path)

    while destination.exists():
        print(f"File path {destination} already exists. Creating new filepath.")
        logging.warning(f"File path {destination} already exists. Creating new filepath.")
        main_csv_file_full_path = f"{mainCsv_file_dir}\\{main_csv_file_name_parts[0]}_{ID_number}.{main_csv_file_name_parts[1]}"
        destination = Path(main_csv_file_full_path) 
        print(f"New file path is {destination}")
        logging.warning(f"New file path is {destination}")
        ID_number += 1

    shutil.copy2(source, destination)


def CreateTempCsvLF(app: pf.Application, LF_file: str):
    '''
    This function creates a readable csv file for loadflow 
    '''
    assert(type(app) == pf.Application), "The Argument 'app' is not of type powerfactory.application"
    assert(type(LF_file) == str), "The Argument 'LF_file' is not of type str"

    oComLdf = app.GetFromStudyCase("ComLdf")
    oComShc = app.GetFromStudyCase("ComShc")

    oComLdf.Execute()

    sTerm = app.GetCalcRelevantObjects("*.ElmTerm")
    sLne = app.GetCalcRelevantObjects("*.ElmLne")
    sGen = app.GetCalcRelevantObjects("*.ElmSym")
    sLod = app.GetCalcRelevantObjects("*.ElmLod")

    TermNameLst, VoltAmpLst, VoltAngLst = STATIC.GetTermVolt(sTerm)
    GenNameLst,GenActLst, GenReactLst = STATIC.GetGenPower(sGen)
    LodNameLst, LodActLst, LodReactLst = STATIC.GetLodPower(sLod)
    GenNameLst2, GenStatusLst = STATIC.GetGenTopology(sGen)
    LneNameLst2, LneStatusLst = STATIC.GetLineTopology(sLne)

    oComShc.Execute()

    TermNameLst2, TermShcLst = STATIC.GetTermShc(sTerm)

    file = open(LF_file, "w+", encoding = "utf-8")

    for i in range(len(TermNameLst)):
        file.write("U_%s_[pu];phi_%s_[deg];" % (TermNameLst[i], TermNameLst[i]))
    for i in range(len(GenNameLst)):
        file.write("P_%s_[MW];Q_%s_[MVAr];" % (GenNameLst[i], GenNameLst[i]))
    for i in range(len(LodNameLst)):
        file.write("P_%s_[MW];Q_%s_[MVAr];" % (LodNameLst[i], LodNameLst[i]))
    for i in range(len(GenNameLst2)):
        file.write("oserv_%s;" % GenNameLst2[i])
    for i in range(len(LneNameLst2)):
        file.write("oserv_%s;" % LneNameLst2[i])
    for i in range(len(TermNameLst2)):
        file.write("Sk_%s_[MVA]" % TermNameLst2[i].replace("_", "\\"))
        if i != len(TermNameLst2) - 1:
            file.write(";")

    file.write("\n")

    for i in range(len(TermNameLst)):
        currVAmp = floatToStr(VoltAmpLst[i],4)
        currVAng = floatToStr(VoltAngLst[i],2)
        file.write("%s;%s;" % (currVAmp, currVAng))

    for i in range(len(GenNameLst)):
        currGenAct = floatToStr(GenActLst[i], 2)
        currGenReact = floatToStr(GenReactLst[i], 2)
        file.write("%s;%s;" % (currGenAct, currGenReact))

    for i in range(len(LodNameLst)):
        currLodAct = floatToStr(LodActLst[i], 2)
        currLodReact = floatToStr(LodReactLst[i], 2)
        file.write("%s;%s;" % (currLodAct, currLodReact))

    for i in range(len(GenNameLst2)):
        file.write("%i;" % GenStatusLst[i])

    for i in range(len(LneNameLst2)):
        file.write("%i;" % LneStatusLst[i])

    for i in range(len(TermNameLst2)):
        currTermShc = floatToStr(TermShcLst[i], 2)
        file.write("%s" % currTermShc)
        if i != len(TermShcLst) - 1:
            file.write(";")

    file.close()

    return(True)

def CreateTempCsvLFSLO(app: pf.Application, LF_file: str):
    '''
    This function creates a readable csv file for loadflow 
    '''
    assert(type(app) == pf.Application), "The Argument 'app' is not of type powerfactory.application"
    assert(type(LF_file) == str), "The Argument 'LF_file' is not of type str"

    oComLdf = app.GetFromStudyCase("ComLdf")
    oComShc = app.GetFromStudyCase("ComShc")

    oComLdf.Execute()

    sTerm = app.GetCalcRelevantObjects("*.ElmTerm")
    sLne = app.GetCalcRelevantObjects("*.ElmLne")
    sGen = app.GetCalcRelevantObjects("*.ElmSym")
    sLod = app.GetCalcRelevantObjects("*.ElmLod")

    TermNameLst, VoltAmpLst, VoltAngLst = STATIC.GetTermVoltSLO(sTerm)
    GenNameLst,GenActLst, GenReactLst = STATIC.GetGenPowerSLO(sGen)
    LneNameLst, LneP1Lst, LneQ1Lst, LneP2Lst, LneQ2Lst = STATIC.GetLineFlowsSLO(sLne)
    LodNameLst, LodActLst, LodReactLst = STATIC.GetLodPowerSLO(sLod)
    GenNameLst2, GenStatusLst = STATIC.GetGenTopologySLO(sGen)
    LneNameLst2, LneStatusLst = STATIC.GetLineTopologySLO(sLne)

    oComShc.SetAttribute("iopt_mde", 1)
    oComShc.SetAttribute("iopt_allbus", 2)
    oComShc.Execute()

    TermNameLst2, TermShcLst = STATIC.GetTermShc(sTerm)

    file = open(LF_file, "w+", encoding = "utf-8")

    for i in range(len(TermNameLst)):
        CurrTermName = returnAfterChar(TermNameLst[i], " ")
        CurrTermName = replaceWeirdChars(CurrTermName)
        file.write("U_%s_[pu];phi_%s_[deg];" % (CurrTermName, CurrTermName))
    for i in range(len(LneNameLst)):
        CurrLneName = returnAfterChar(LneNameLst[i], " ")
        CurrLneName = replaceWeirdChars(CurrLneName)
        file.write("P1_%s_[MW];Q1_%s_[MVAr];P2_%s_[MW];Q2_%s_[MVAr];" % (CurrLneName, CurrLneName, CurrLneName, CurrLneName))
    for i in range(len(GenNameLst)):
        CurrGenName = returnAfterChar(GenNameLst[i], " ")
        CurrGenName = replaceWeirdChars(CurrGenName)
        file.write("P_%s_[MW];Q_%s_[MVAr];" % (CurrGenName, CurrGenName))
    for i in range(len(LodNameLst)):
        CurrLodName = returnAfterChar(LodNameLst[i], " ")
        CurrLodName = replaceWeirdChars(CurrLodName)
        file.write("P_%s_[MW];Q_%s_[MVAr];" % (CurrLodName, CurrLodName))
    for i in range(len(GenNameLst2)):
        CurrGenName = returnAfterChar(GenNameLst2[i], " ")
        CurrGenName = replaceWeirdChars(CurrGenName)
        file.write("oserv_%s;" % CurrGenName)
    for i in range(len(LneNameLst2)):
        CurrLneName = returnAfterChar(LneNameLst2[i], " ")
        CurrLneName = replaceWeirdChars(CurrLneName)
        file.write("oserv_%s;" % CurrLneName)
    for i in range(len(TermNameLst2)):
        CurrTermName = returnAfterChar(TermNameLst2[i], " ")
        CurrTermName = replaceWeirdChars(CurrTermName)
        file.write("Sk_%s_[MVA]" % CurrTermName)
        if i != len(TermNameLst2) - 1:
            file.write(";")

    file.write("\n")

    for i in range(len(TermNameLst)):
        currVAmp = floatToStr(VoltAmpLst[i],4)
        currVAng = floatToStr(VoltAngLst[i],2)
        file.write("%s;%s;" % (currVAmp, currVAng))

    for i in range(len(LneNameLst)):
        CurrP1 = floatToStr(LneP1Lst[i],2)
        CurrQ1 = floatToStr(LneQ1Lst[i],2)
        CurrP2 = floatToStr(LneP2Lst[i],2)
        CurrQ2 = floatToStr(LneQ2Lst[i],2)
        file.write("%s;%s;%s;%s;" % (CurrP1, CurrQ1, CurrP2, CurrQ2))

    for i in range(len(GenNameLst)):
        currGenAct = floatToStr(GenActLst[i], 2)
        currGenReact = floatToStr(GenReactLst[i], 2)
        file.write("%s;%s;" % (currGenAct, currGenReact))

    for i in range(len(LodNameLst)):
        currLodAct = floatToStr(LodActLst[i], 2)
        currLodReact = floatToStr(LodReactLst[i], 2)
        file.write("%s;%s;" % (currLodAct, currLodReact))

    for i in range(len(GenNameLst2)):
        file.write("%i;" % GenStatusLst[i])

    for i in range(len(LneNameLst2)):
        file.write("%i;" % LneStatusLst[i])

    for i in range(len(TermNameLst2)):
        currTermShc = floatToStr(TermShcLst[i], 2)
        file.write("%s" % currTermShc)
        if i != len(TermShcLst) - 1:
            file.write(";")

    file.close()

    return(True)

def CreateTempCsvPQiff(file_name: str, PDiffRes: dict):
    '''
    This function creates a temporary .csv file in which the static power difference data is stored.
    '''

    assert(type(file_name) == str), "Argument 'file_name' is not of type string"
    assert(type(PDiffRes) == dict), "Argument 'PDiffRes' is not of type dictinoary"
    
    Keys = list(PDiffRes.keys())

    headerStr = ""
    dataStr = ""
    for iKey in range(len(Keys)):
        ResLst = PDiffRes[Keys[iKey]]
        KeyNumber = 1
        for iRes in range(len(ResLst)):
            PRes = str(ResLst[iRes][0]).replace(".",",")
            QRes = str(ResLst[iRes][1]).replace(".",",")
            headerStr = headerStr+Keys[iKey]+"_"+str(KeyNumber)+"_Pdiff;"+Keys[iKey]+"_"+str(KeyNumber)+"_Qdiff"
            dataStr = dataStr+PRes+";"+QRes
            if iRes != len(ResLst)-1:
                headerStr = headerStr+";"
                dataStr = dataStr+";"
            KeyNumber = KeyNumber + 1
        if iKey != len(Keys)-1:
            headerStr = headerStr+";"
            dataStr = dataStr+";"

    file = open(file_name,"w", encoding = "utf-8")
    file.write(headerStr)
    file.write("\n")
    file.write(dataStr)
    file.close

def CreateTempCsvPQdiffv2(file_name: str, PQdiffRes: dict):
    '''
    This function creates a temporary .csv file in which the static power difference data is stored.
    '''

    assert(type(file_name) == str), "Argument 'file_name' is not of type string"
    assert(type(PQdiffRes) == dict), "Argument 'PQdiffRes' is not of type dictionary"


    Keys = list(PQdiffRes.keys())

    ForNameLst = PQdiffRes["for_names"]

    headerStr = ""
    dataStr = ""

    for ind in range(len(ForNameLst)):
        for key in Keys:
            currEntry = PQdiffRes[key][ind]
            if type(currEntry) == float:
                currEntry = floatToStr(currEntry)
            headerStr = headerStr+key+"_"+str(ind)
            dataStr = dataStr+currEntry
            if key != Keys[-1]:
                headerStr = headerStr+";"
                dataStr = dataStr+";"
        if ind != len(ForNameLst)-1:
            headerStr = headerStr+";"
            dataStr = dataStr+";"

    with open(file_name, 'w', encoding = "utf-8") as file:
        file.write(headerStr)
        file.write("\n")
        file.write(dataStr)

def CreateTempCsvPQdiffv3(file_name: str, Udiff: float, Pdiff: float, Qdiff: float) -> bool:
    '''
    This function creates a temporary .csv file in which the static power difference data is stored.
    '''

    assert(type(file_name) == str), "Argument 'file_name' is not of type string"
    assert(isinstance(Udiff, numbers.Number)), "Argument 'Udiff' is not a number type"
    assert(isinstance(Pdiff, numbers.Number)), "Argument 'Pdiff' is not a number type"
    assert(isinstance(Qdiff, numbers.Number)), "Argument 'Qdiff' is not a number type"

    headerStr = "Absolute_Relative_Voltage_Difference;Absolute_Relative_Active_Power_Difference;Absolute_Relative_Reactive_Power_Difference"
    dataStr = f"{Udiff:.5f},{Pdiff:.5f},{Qdiff:.5f}"

    with open(file_name, 'w', encoding = "utf-8") as file:
        file.write(headerStr)
        file.write("\n")
        file.write(dataStr)

    return True

def CreateTempCsvTSA(file_name: str, CCTs: list):
    '''
    This function creates a temporary .csv file in which the current simulation results are stored.
    ''' 
    assert(type(file_name) == str), "Given Argument 'file' is not a string"
    assert(type(CCTs) == list), "Given Argument 'CCTs' is not a list"
    for i in range(len(CCTs)):
        assert(type(CCTs[i]) == list), "Entry of 'CCTs' in postion "+str(i)+" is not a list type"
        assert(len(CCTs[i]) == 5), "length of entry of 'CCTs' in position "+str(i)+" is not 5"
        assert(type(CCTs[i][0]) in [int, float]), "Type of CCTs["+str(i)+"][0] is not int or float"
        assert(type(CCTs[i][1]) == str), "Type of CCTs["+str(i)+"][1] is not string"
        assert(type(CCTs[i][2]) in [str,int]), "Type of CCTs["+str(i)+"][2] is not string or int"
        assert(CCTs[i][3] in [0, 1]), "Entry CCTs["+str(i)+"][3] is not 0 or 1"
        assert(type(CCTs[i][4]) == str), "Type of CCTs["+str(i)+"][4] is not string"

    file = open(file_name, "w+", encoding = "utf-8")
    for i in range(len(CCTs)):    
        file.write("CCT_%i;Terminal_%i;Crit_gen_%i;Type_%i;Location_%i" % (i, i, i, i, i)) # write header
        if i != len(CCTs)-1:
            file.write(";")
    file.write("\n")
    for i in CCTs:
        currCritFaultTime = floatToStr(i[0])
        currTermName = i[1].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
        if i[2] != 0:
            currCritGenName = i[2].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
        else: currCritGenName = "None"
        currFaultType = i[3]
        currFaultLocation = i[4].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
        file.write("%s;%s;%s;%i;%s" % (currCritFaultTime, currTermName, currCritGenName, currFaultType, currFaultLocation)) # write information
        if i != CCTs[-1]:
            file.write(";")
    file.close()

def CreateTempCsvSSSA(full_SSSA_file: str, temp_SSSA_file: str, Gen_record_SSSA: list):
    '''
    This funciton creates a readable csv file out of the unreadable powerfactory file
    '''
    assert(type(full_SSSA_file) == str), "The Argument 'full_SSSA_file' is not a string"
    assert(type(temp_SSSA_file) == str), "The Argument 'temp_SSSA_file' is not a string"
    assert(type(Gen_record_SSSA) == list), "The Argument 'Gen_record_SSSA' is not a list"

    full_db = pd.read_csv(full_SSSA_file, sep = ";", skiprows=[1], encoding = "utf-8", low_memory=False)

    Recorded_gens = []
    col_num = 0
    for i in full_db.columns:
        if (col_num == 1):
            RealCol = i
        if (col_num == 2):
            ImagCol = i
        for j in Gen_record_SSSA:
            if (j in i) and not (j in Recorded_gens):
                Recorded_gens.append(j)
        col_num = col_num + 1

    Redorded_gen_cols = []
    for i in Recorded_gens:
        curr_gen_cols = [col for col in full_db.columns if i in col]
        Redorded_gen_cols.append(curr_gen_cols)

    file1 = open(temp_SSSA_file, "w+", encoding = "utf-8")

    for row in full_db.index:
        file1.write("RealPart_Mode%i;ImagPart_Mode%i;" % (row, row))
        for i in Recorded_gens:
            if "_" in i:
                i.replace("_","")
            file1.write("ConMag_Mode%i_%s;ConAng_Mode%i_%s;" % (row, i, row, i))
            file1.write("ObsMag_Mode%i_%s;ObsAng_Mode%i_%s;" % (row, i, row, i))
            file1.write("ParMag_Mode%i_%s;ParAng_Mode%i_%s" % (row, i, row, i))
            if i != Recorded_gens[-1]:
                file1.write(";")
        if row != full_db.index[-1]:
            file1.write(";")

    file1.write("\n")

    for row in full_db.index:
        currReal = full_db[RealCol][row]
        currImag = full_db[ImagCol][row]
        file1.write("%s;%s;" % (currReal, currImag))
        for i in Redorded_gen_cols:
            currConMag = full_db[i[-12]][row]
            currConAmp = full_db[i[-11]][row]
            currObsMag = full_db[i[-10]][row]
            currObsAng = full_db[i[-9]][row]
            currParMag = full_db[i[-8]][row]
            currParAng = full_db[i[-7]][row]
            file1.write("%s;%s;" % (currConMag, currConAmp))
            file1.write("%s;%s;" % (currObsMag, currObsAng))
            file1.write("%s;%s" % (currParMag, currParAng))
            if i != Redorded_gen_cols[-1]:
                file1.write(";")
        if row != full_db.index[-1]:
            file1.write(";")

    file1.close()

def CreateTempCsvSSSAv2(full_SSSA_file: str, temp_SSSA_file:str, Gen_record_SSSA: list, EV_par_settings: list):
    '''
    This funciton creates a readable csv file out of the unreadable powerfactory file.
    Some shrotcommings from the original function have been fixed.
    '''
    assert(type(full_SSSA_file) == str), "The Argument 'full_SSSA_file' is not a string"
    assert(type(temp_SSSA_file) == str), "The Argument 'temp_SSSA_file' is not a string"
    assert(type(Gen_record_SSSA) == list), "The Argument 'Gen_record_SSSA' is not a list"
    assert(isinstance(EV_par_settings, Iterable)), "The Argument 'EV_par_sum' is not a an iterable"
    for i, EV_stat in enumerate(EV_par_settings):
        assert(EV_stat in [0, 1]), f"The argument 'EV_par_settings[{i}]' is not 0 or 1."

    full_db = pd.read_csv(full_SSSA_file, sep = ";", skiprows=[1], encoding="utf-8", low_memory=False)
    EV_par_sum = sum(EV_par_settings)

    Recorded_gens = []
    col_num = 0
    for i in full_db.columns:
        if (col_num == 1):
            RealCol = i
        if (col_num == 2):
            ImagCol = i
        for j in Gen_record_SSSA:
            if (j in i) and not (j in Recorded_gens):
                Recorded_gens.append(j)
        col_num = col_num + 1

    Recorded_gen_cols = []
    for i in Recorded_gens:
        curr_gen_cols = [col for col in full_db.columns if i in col]
        if len(curr_gen_cols) not in [EV_par_sum*10,EV_par_sum*12]:
            print(f"Modal analysis detectected that generator {i} does not have {EV_par_sum*10} or {EV_par_sum*12} entries. Expected are {EV_par_sum*10} or {EV_par_sum*12} entries (5 state variables -psi1, psifd, psi1q, speed, phi x 2 vector values - Magnitude, Angle x {EV_par_sum} modal values - either Controllability, Observability, Participarion factor)")
        Recorded_gen_cols.append(curr_gen_cols)

    # create the save strings
    header_string = ""
    data_string = ""

    # file1 = open(temp_SSSA_file, "w+", encoding = "utf-8")

    for row in full_db.index:
        header_string += "RealPart_Mode%i;ImagPart_Mode%i;" % (row, row)
        currReal = full_db[RealCol][row]
        currImag = full_db[ImagCol][row]
        data_string += "%s;%s;" % (currReal, currImag)

        for i in Recorded_gens:
            for j in Recorded_gen_cols:
                if i in j[0]:
                    curr_gen_col_len = len(j)
                    break
            if "_" in i:
                i.replace("_","")
            if curr_gen_col_len == EV_par_sum*10:
                for k in ["Psi1d","Psifd","Psi1q","speed","phi"]:
                    if EV_par_settings[0] == 1:
                        header_string += "ConMag_Mode%i_%s_%s;ConAng_Mode%i_%s_%s;" % (row, k, i, row, k, i)
                    if EV_par_settings[1] == 1:
                        header_string += "ObsMag_Mode%i_%s_%s;ObsAng_Mode%i_%s_%s;" % (row, k, i, row, k, i)
                    if EV_par_settings[2] == 1:
                        header_string += "ParMag_Mode%i_%s_%s;ParAng_Mode%i_%s_%s" % (row, k, i, row, k, i)
                    if k != "phi":
                        header_string += ";"
                for col_name in j:
                    curr_val = full_db[col_name][row]
                    data_string += "%s" % curr_val
                    if col_name != j[-1]:
                        data_string += ";"
            elif curr_gen_col_len == EV_par_sum*12:
                for k in ["Psi1d","Psifd","Psi1q","Psi2q","speed","phi"]:
                    if EV_par_settings[0] == 1:
                        header_string += "ConMag_Mode%i_%s_%s;ConAng_Mode%i_%s_%s;" % (row, k, i, row, k, i)
                    if EV_par_settings[1] == 1:
                        header_string += "ObsMag_Mode%i_%s_%s;ObsAng_Mode%i_%s_%s;" % (row, k, i, row, k, i)
                    if EV_par_settings[2] == 1:
                        header_string += "ParMag_Mode%i_%s_%s;ParAng_Mode%i_%s_%s" % (row, k, i, row, k, i)
                    if k != "phi":
                        header_string +=";"
                for col_name in j:
                    curr_val = full_db[col_name][row]
                    data_string += "%s" % curr_val
                    if col_name != j[-1]:
                        data_string += ";"
            else:
                print(f"couldn't find appropriate column for gen {i}.")
                continue
            if i != Recorded_gens[-1]:
                header_string +=";"
                data_string += ";"
        if row != full_db.index[-1]:
            header_string +=";"
            data_string += ";"

    with open(temp_SSSA_file, "w+", encoding = "utf-8") as file1:
        file1.write(header_string)
        file1.write("\n")
        file1.write(data_string)

    # THE FOLLOWING CODE DOESN'T WORK. IT IS HERE AS AN EXAMPLE OF WRONG CODE USED FOR SSSA EXTRACTION

    # file1 = open(temp_SSSA_file, "w+", encoding = "utf-8")

    # for row in full_db.index:
    #     file1.write("RealPart_Mode%i;ImagPart_Mode%i;" % (row, row))
    #     for i in Recorded_gens:
    #         for j in Recorded_gen_cols:
    #             if i in j[0]:
    #                 curr_gen_col_len = len(j)
    #         if "_" in i:
    #             i.replace("_","")
    #         if curr_gen_col_len == EV_par_sum*10:
    #             for k in ["Psi1d","Psifd","Psi1q","speed","phi"]:
    #                 if EV_par_settings[0] == 1:
    #                     file1.write("ConMag_Mode%i_%s_%s;ConAng_Mode%i_%s_%s;" % (row, k, i, row, k, i))
    #                 if EV_par_settings[1] == 1:
    #                     file1.write("ObsMag_Mode%i_%s_%s;ObsAng_Mode%i_%s_%s;" % (row, k, i, row, k, i))
    #                 if EV_par_settings[2] == 1:
    #                     file1.write("ParMag_Mode%i_%s_%s;ParAng_Mode%i_%s_%s" % (row, k, i, row, k, i))
    #                 if k != "phi":
    #                     file1.write(";")
    #         elif curr_gen_col_len == EV_par_sum*12:
    #             for k in ["Psi1d","Psifd","Psi1q","Psi2q","speed","phi"]:
    #                 if EV_par_settings[0] == 1:
    #                     file1.write("ConMag_Mode%i_%s_%s;ConAng_Mode%i_%s_%s;" % (row, k, i, row, k, i))
    #                 if EV_par_settings[1] == 1:
    #                     file1.write("ObsMag_Mode%i_%s_%s;ObsAng_Mode%i_%s_%s;" % (row, k, i, row, k, i))
    #                 if EV_par_settings[2] == 1:
    #                     file1.write("ParMag_Mode%i_%s_%s;ParAng_Mode%i_%s_%s" % (row, k, i, row, k, i))
    #                 if k != "phi":
    #                     file1.write(";")
    #         else:
    #             print(f"couldn't find appropriate column for gen {i}.")
    #             continue
    #         if i != Recorded_gens[-1]:
    #             file1.write(";")
    #     if row != full_db.index[-1]:
    #         file1.write(";")

    # file1.write("\n")

    # for row in full_db.index:
    #     currReal = full_db[RealCol][row]
    #     currImag = full_db[ImagCol][row]
    #     file1.write("%s;%s;" % (currReal, currImag))
    #     for i in Recorded_gen_cols:
    #         for j in i:
    #             curr_val = full_db[j][row]
    #             file1.write("%s" % curr_val)
    #             if j != i[-1]:
    #                 file1.write(";")
    #         if i != Recorded_gen_cols[-1]:
    #             file1.write(";")
    #     if row != full_db.index[-1]:
    #         file1.write(";")

    # file1.close()

def CreateTempCsvFSA(file_name: str, FSA_results: str, Mlim: list, Hdata: list):
    '''
    This function creates a temporary .csv file in which the current simulation results are stored.
    ''' 
    assert(type(file_name) == str), "Argument 'file_name' is not of type str"
    assert(type(FSA_results) == list), "Argument 'FSA_results' is not of type list"
    for i in range(len(FSA_results)):
        for j in range(len(FSA_results[i])):
            if j == 0:
                assert(type(FSA_results[i][j]) == str), "Argument 'FSA_results["+str(i)+"][0] is not of type string"
            else:
                assert(type(FSA_results[i][j][0]) == str), "Argument 'FSA_results["+str(i)+"]["+str(j)+"][0] is not of type string"
                assert(type(FSA_results[i][j][1]) in [int, float]), "Argument 'FSA_results["+str(i)+"]["+str(j)+"][1]' is not of type int or float"
                assert(type(FSA_results[i][j][2]) in [int, float]), "Argument 'FSA_results["+str(i)+"]["+str(j)+"][2]' is not of type int or float"
                assert(type(FSA_results[i][j][3]) in [int, float]), "Argument 'FSA_results["+str(i)+"]["+str(j)+"][3]' is not of type int or float"
                assert(type(FSA_results[i][j][4]) == list), "Argument 'FSA_results["+str(i)+"]["+str(j)+"][4]' is not of type list"
                for k in range(len(FSA_results[i][j][4])):
                    assert(type(FSA_results[i][j][4][k]) in [int, float]), "Argument 'FSA_results["+str(i)+"]["+str(j)+"][4]["+str(k)+"]' is not of type int or float"
    for i in range(len(Mlim)):
        assert(type(Mlim[i]) in [int,float]), "Argument 'Mlim["+str(i)+"] should be of type int or float"
    assert(type(Hdata) == list), "Argument Hdata is not of type list."
    for i, Hdata_entry in enumerate(Hdata):
        assert(type(Hdata_entry) in [float,int]), "Argument Hdata["+str(i)+"] is not of type float or int."

    # write header
    file = open(file_name, "w+", encoding = "utf-8")

    # write inertia data
    file.write("Wktotal_[MWs];Htotal_[s];HCoI_[s];Wkmax[MWs];Hmax[s];")

    # write MThresholds
    for i in range(len(Mlim)):
        file.write("MThreshold%i;" % (i+1))
    
    for i in range(len(FSA_results)):
        currGenOut = FSA_results[i][0].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
        for j in range(len(FSA_results[i])):
            if j == 0:
                continue
            else:
                currGenMon = FSA_results[i][j][0].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
                file.write("minF_%s_%s;" % (currGenOut, currGenMon))
                file.write("maxF_%s_%s;" % (currGenOut, currGenMon))
                file.write("maxRoCoF_%s_%s;" % (currGenOut, currGenMon))
                for k in range(len(Mlim)):
                    file.write("M%i_%s_%s" % (k+1, currGenOut, currGenMon))
                    if k != len(Mlim)-1:
                        file.write(";")
            if j != len(FSA_results[i])-1:
                file.write(";")
        if i != len(FSA_results)-1:
            file.write(";")
    
    #line break
    file.write("\n")

    # write values
    Wktotal = floatToStr(Hdata[0], rounding='floor')
    Htotal = floatToStr(Hdata[1], rounding='floor')
    HCoI = floatToStr(Hdata[2], rounding='floor')
    Wkmax = floatToStr(Hdata[3], rounding='floor')
    Hmax = floatToStr(Hdata[4], rounding='floor')
    file.write(f"{Wktotal};{Htotal};{HCoI};{Wkmax};{Hmax};")

    for i in Mlim:
        file.write("%s;" % floatToStr(i, dec = 2))
    
    for i in range(len(FSA_results)):
        for j in range(len(FSA_results[i])):
            if j == 0:
                continue
            else:
                currMinF = floatToStr(FSA_results[i][j][1], dec = 4, rounding="floor")
                currMaxF = floatToStr(FSA_results[i][j][2], dec = 4, rounding="ceil")
                currMaxRoCoF = floatToStr(FSA_results[i][j][3], dec = 4, rounding="ceil")
                file.write("%s;%s;%s;" % (currMinF, currMaxF, currMaxRoCoF))
                for k in range(len(Mlim)):
                    currM = floatToStr(FSA_results[i][j][4][k], dec=4, rounding="floor")
                    file.write("%s" % currM)
                    if k != len(Mlim)-1:
                        file.write(";")
            if j != len(FSA_results[i])-1:
                file.write(";")
        if i != len(FSA_results):
            file.write(";")

    file.close()

def CreateTempCsvFSA2(file_name: str, FSA_results: str, RoCoFWindowList: list, Hdata: list):
    '''
    This function creates a temporary .csv file in which the current simulation results are stored.
    ''' 
    assert(type(file_name) == str), "Argument 'file_name' is not of type str"
    assert(isinstance(FSA_results, Iterable)), "Argument 'FSA_results' is not an Iterable."
    for i , FSA_result_list in enumerate(FSA_results):
        for j, FSA_case_res in enumerate(FSA_result_list):
            if j == 0:
                assert(isinstance(FSA_case_res, str)), f"Argument 'FSA_results[{i}][{j}] is not of type string."
            else:
                assert(isinstance(FSA_case_res[0], str)), f"Argument 'FSA_results[{i}][{j}[0] is not of type string."
                assert(isinstance(FSA_case_res[1], (int, float))), f"Argument 'FSA_results[{i}][{j}[1] is not a number."
                assert(isinstance(FSA_case_res[2], (int, float))), f"Argument 'FSA_results[{i}][{j}[2] is not a number."
                assert(isinstance(FSA_case_res[3], Iterable)), f"Argument 'FSA_results[{i}][{j}[3] is not an iterable."
                for k, RoCoFRes in enumerate(FSA_case_res[3]):
                    assert(isinstance(RoCoFRes, (int, float))), f"Argument 'FSA_results[{i}][{j}[3][{k}] is not a number."
    for i, RoCoFWindow in enumerate(RoCoFWindowList):
        assert(isinstance(RoCoFWindow, (int, float))), f"Argument 'RoCoFWindowList[{i}]' is not a number"
    assert(isinstance(Hdata, Iterable)), "Argument Hdata is not an iterable."
    for i, Hdata_entry in enumerate(Hdata):
        assert(isinstance(Hdata_entry, (int, float))), f"Argument Hdata[{i}] is not of type float or int."

    # write header
    file = open(file_name, "w+", encoding = "utf-8")

    # write inertia data
    file.write("Wktotal_[MWs];Htotal_[s];HCoI_[s];Wkmax[MWs];Hmax[s];")
    
    for i, FSA_result_list in enumerate(FSA_results):
        currGenOut = FSA_result_list[0].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
        for j, FSA_case_res in enumerate(FSA_result_list):
            if j == 0:
                continue
            else:
                currGenMon = FSA_case_res[0].replace("_","") # the replace statement is there to avoid confusion with the "_" seperating values in the final database
                file.write("minF_%s_%s;" % (currGenOut, currGenMon))
                file.write("maxF_%s_%s;" % (currGenOut, currGenMon))
                for k, RoCoFWindow in enumerate(RoCoFWindowList):
                    RoCoFDelayInt = int(RoCoFWindow*1000)
                    file.write("maxRoCoF_%sms_%s_%s" % (RoCoFDelayInt, currGenOut, currGenMon))
                    if k != len(RoCoFWindowList)-1:
                        file.write(";")
            if j != len(FSA_result_list)-1:
                file.write(";")
        if i != len(FSA_results)-1:
            file.write(";")
    
    #line break
    file.write("\n")

    # write values
    Wktotal = floatToStr(Hdata[0], rounding='floor')
    Htotal = floatToStr(Hdata[1], rounding='floor')
    HCoI = floatToStr(Hdata[2], rounding='floor')
    Wkmax = floatToStr(Hdata[3], rounding='floor')
    Hmax = floatToStr(Hdata[4], rounding='floor')
    file.write(f"{Wktotal};{Htotal};{HCoI};{Wkmax};{Hmax};")
    
    for i, FSA_result_list in enumerate(FSA_results):
        for j, FSA_case_res in enumerate(FSA_result_list):
            if j == 0:
                continue
            else:
                currMinF = floatToStr(FSA_case_res[1], dec = 4, rounding="floor")
                currMaxF = floatToStr(FSA_case_res[2], dec = 4, rounding="ceil")
                file.write("%s;%s;" % (currMinF, currMaxF))
                for k, RoCoFRes in enumerate(FSA_case_res[3]):
                    currRoCoF = floatToStr(RoCoFRes, dec=4, rounding="floor")
                    file.write("%s" % currRoCoF)
                    if k != len(FSA_case_res[3])-1:
                        file.write(";")
            if j != len(FSA_result_list)-1:
                file.write(";")
        if i != len(FSA_results):
            file.write(";")

    file.close()

def CreateTempCsvDate(file_name: str, date: str):
    '''
    This funciton creates a temporary .csv file in which the date of the current simulation is stored
    '''
    
    file = open(file_name, "w", encoding = "utf-8")
    file.write(";DateTime")
    file.write("\n")
    file.write("0;%s" % date)

def CreateTempCsvInfo(file_name: str, MethodUsed: tuple[tuple], ExecutionTime: list, settingsTSA: list, settingsFSA: list, settingsSSSA: list):
    '''
    This function creates a temporary .csv in which the settings if the current simualtion are stored.
    
    :param file_name: Name of the file to save to
    :param MethodUsed: Methods used for simulations - see fullDSA.py lines 158-173 for full description
    :param ExecutionTime: Execution time for all sections
    :param settingsTSA: settings used for TSA simulations
    :param settingsFSA: settings used for FSA simulations
    :param settingsSSSA: settings used for SSSA simulatinos
    '''


    file = open(file_name, "w", encoding = "utf-8")
    # header
    file.write("MethodUsed;ExecutionTime;sectionTiming;settingsTSA;settingsFSA;settingsSSSA")
    # info
    file.write("\n")
    # Methods used
    writeIterable(file, MethodUsed)
    # Total execution time
    TotalExecutionTime = ExecutionTime[-1]-ExecutionTime[0]
    file.write(";%s" % TotalExecutionTime)
    # sectionTiming
    file.write(";")
    match MethodUsed[1]:
        case 0:
            Imoport_time = ExecutionTime[1]-ExecutionTime[0]
            list_setup_time = ExecutionTime[2]-ExecutionTime[1]
            initialisation_time = ExecutionTime[3]-ExecutionTime[2]
            LF_calc_time = ExecutionTime[4]-ExecutionTime[3]
            Freerun_time = ExecutionTime[5]-ExecutionTime[4]
            TSA_time =   ExecutionTime[6]-ExecutionTime[5] 
            FSA_time =   ExecutionTime[7]-ExecutionTime[6]
            SSSA_time =   ExecutionTime[8]-ExecutionTime[7]  
            export_time =   ExecutionTime[9]-ExecutionTime[8]
            total_times = (Imoport_time, list_setup_time, initialisation_time, LF_calc_time, Freerun_time, TSA_time, FSA_time, SSSA_time, export_time)    
        case 1:
            Imoport_time = ExecutionTime[1]-ExecutionTime[0]
            list_setup_time = ExecutionTime[2]-ExecutionTime[1]
            initialisation_time = ExecutionTime[3]-ExecutionTime[2]
            LF_calc_time = ExecutionTime[4]-ExecutionTime[3]
            Freerun_time = ExecutionTime[5]-ExecutionTime[4]
            TSA_and_FSA_time = ExecutionTime[6]-ExecutionTime[5]
            SSSA_time =   ExecutionTime[7]-ExecutionTime[6]  
            export_time =   ExecutionTime[8]-ExecutionTime[7]
            total_times = (Imoport_time, list_setup_time, initialisation_time, LF_calc_time, Freerun_time, TSA_and_FSA_time, SSSA_time, export_time)
    writeIterable(file, total_times)
    # settings for TSA
    file.write(";")
    writeIterable(file, settingsTSA)
    # settings for FSA
    file.write(";")
    writeIterable(file, settingsFSA)
    # settings for SSSA
    file.write(";")
    writeIterable(file, settingsSSSA)
    file.close()

def CreateTempCsvInfov2(file_name: str, DateTime: str, MethodUsed: tuple[tuple], ExecutionTime: list, settingsTSA: list, settingsFSA: list, settingsSSSA: list):
    '''
    This function creates a temporary .csv in which the settings if the current simualtion are stored.
    
    :param file_name: Name of the file to save to
    :param DateTime: Datetime of the operation scenario simulated
    :param MethodUsed: Methods used for simulations - see fullDSA.py lines 158-173 for full description
    :param ExecutionTime: Execution time for each section
    :param settingsTSA: settings used for TSA simulations
    :param settingsFSA: settings used for FSA simulations
    :param settingsSSSA: settings used for SSSA simulatinos
    '''


    file = open(file_name, "w", encoding = "utf-8")
    # header
    file.write("DateTime;MethodUsed;ExecutionTime;settingsTSA;settingsFSA;settingsSSSA;TimeStats")
    # info
    file.write("\n")
    # DateTime
    file.write("%s" % DateTime)
    # Methods used
    file.write(";")
    writeIterable(file, MethodUsed)
    # Total execution time
    TotalExecutionTime = ExecutionTime[-1]-ExecutionTime[0]
    file.write(";%s" % TotalExecutionTime)
    # settings for TSA
    file.write(";")
    writeIterable(file, settingsTSA)
    # settings for FSA
    file.write(";")
    writeIterable(file, settingsFSA)
    # settings for SSSA
    file.write(";")
    writeIterable(file, settingsSSSA)
    file.close()

#used for analysis
def CreateOAFixPQDeltaCsv(file_name: str, GenAdjustmentDict: dict) -> bool:
    with open(file_name, "w") as f:
        dict_keys = GenAdjustmentDict.keys()
        last_key = next(reversed(dict_keys))
        for key in dict_keys:
            f.write(key)
            if key != last_key:
                f.write(";")

        f.write("\n")
        for key in dict_keys:
            f.write(floatToStr(GenAdjustmentDict[key]))
            if key != last_key:
                f.write(";")
