'''
Author: Matjaz Skrlec
date: 14. 10. 2024
version: 1.0
description: This module is used for retrieving the basic results of static simulations.
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import math
import PFSupport.GetElements as GetElements
import powerfactory as pf
from collections.abc import Iterable
from typing import Literal
type Mode = Literal['ceil', 'floor', 'round']

def ExtractForName(ForName: str):
    forIndex = ForName.find(":")
    if forIndex:
        ForName = ForName[forIndex+1:]
    return ForName

def strToFloat(string: str) -> float:
    return(float(string.replace(",",".")))

def getNOfLstEntrys(Lst: list, string: str) -> tuple:
    currInd = 1
    while string+str(currInd) in Lst:
        currInd += 1
    return(currInd)

def getElmBus(oElm: pf.DataObject) -> pf.DataObject:
    oElmCub = oElm.GetAttribute("bus1")
    oElmTerm = oElmCub.GetAttribute("cterm")
    return(oElmTerm)

def getLneBus1(oLne: pf.DataObject) -> pf.DataObject:
    oElmCub = oLne.GetAttribute("bus1")
    if oElmCub:
        oElmTerm = oElmCub.GetAttribute("cterm")
        return(oElmTerm)
    else:
        return(False)

def getLneBus2(oLne: pf.DataObject) -> pf.DataObject:
    oElmCub = oLne.GetAttribute("bus2")
    if oElmCub:
        oElmTerm = oElmCub.GetAttribute("cterm")
        return(oElmTerm)
    else:
        return(False)

def isElmInSLO(Elm: pf.DataObject) -> bool:
    if (Elm.GetAttribute("cpArea")):
        if (Elm.GetAttribute("cpArea").GetAttribute("loc_name") == "SI"):
            return(True)
        else:
            return(False)
    else:
        return(False)
    
def returnAfterChar(string: str, char: str) -> str:
    revStr = string[::-1]
    charCount = 0
    for character in revStr:
        if character == char:
            break
        else:
            charCount += 1
    return(revStr[:charCount][::-1])

def floatToStr(floater: float, dec: int = 2, rounding: Mode = 'round') -> str:
    assert(rounding in ['ceil', 'floor', 'round']), "Invalid entry of argument 'rounding'. Only 'ceil', 'fllor' and 'round' are acceotable."
    correctionNumb = 10**dec
    if rounding == 'round':
        return(str(round(floater*correctionNumb)/correctionNumb).replace(".",","))
    elif rounding == 'ceil':
        return(str(math.ceil(floater*correctionNumb)/correctionNumb).replace(".",","))
    elif rounding == 'floor':
        return(str(math.floor(floater*correctionNumb)/correctionNumb).replace(".",","))

def GetTermVolt(sTerms):
    '''
    This function retrieves the voltage amplitudes and voltage angles of terminals.
    '''

    assert(type(sTerms) == list), "Argument 'sTerms' is not of type list"
    for i in range(len(sTerms)):
        assert(type(sTerms[i]) == pf.DataObject), "Argument 'sTerms["+str(i)+"]' is not of type pf.DataObject"
    
    TermNameLst = []
    VoltAmplLst = []
    VoltAngLst = []
    for oTerm in sTerms:
        if oTerm.GetAttribute("iUsage") == 0:
            if oTerm.GetAttribute("for_name"):
                TermName = oTerm.GetAttribute("for_name").replace("_","")
                TermName = ExtractForName(TermName)
                TermNameLst.append(TermName)

            elif oTerm.cpSubstat:
                SubstatName = oTerm.GetAttribute("cpSubstat").GetAttribute("loc_name").replace("_","")
                TermName = oTerm.GetAttribute("loc_name").replace("_","")
                TermNameLst.append(SubstatName+"\\"+TermName)

            else:
                TermName = oTerm.GetAttribute("loc_name").replace("_","")
                TermNameLst.append(TermName)
            if oTerm.GetAttribute("outserv") == 0:
                VoltAmplLst.append(oTerm.GetAttribute("m:u"))
                VoltAngLst.append(oTerm.GetAttribute("m:phiu"))
            else:
                VoltAmplLst.append(0)
                VoltAngLst.append(0)

    return(TermNameLst, VoltAmplLst, VoltAngLst)


def GetTermVoltSLO(sTerms):
    '''
    This function retrieves the voltage amplitudes and voltage angles of terminals.
    '''

    assert(type(sTerms) == list), "Argument 'sTerms' is not of type list"
    for i in range(len(sTerms)):
        assert(type(sTerms[i]) == pf.DataObject), "Argument 'sTerms["+str(i)+"]' is not of type pf.DataObject"
    
    TermNameLst = []
    VoltAmplLst = []
    VoltAngLst = []
    for oTerm in sTerms:
        if oTerm.GetAttribute("iUsage") == 0:
            if oTerm.GetAttribute("for_name"):
                TermName = oTerm.GetAttribute("for_name").replace("_","")
                TermName = ExtractForName(TermName)
            else:
                if oTerm.cpSubstat:
                    SubstatName = oTerm.GetAttribute("cpSubstat").GetAttribute("loc_name").replace("_","")
                    TermName = oTerm.GetAttribute("loc_name").replace("_","")
                    TermName = SubstatName+"\\"+TermName
                else:
                    TermName = oTerm.GetAttribute("loc_name").replace("_","")
                    TermName = returnAfterChar(TermName, " ")
            TermName = "Bus"+TermName
            if TermName in TermNameLst:
                n_entry = getNOfLstEntrys(TermNameLst, TermName)
                TermNameLst.append(TermName+str(n_entry))
            else:
                TermNameLst.append(TermName)
            if oTerm.GetAttribute("outserv") == 0:
                VoltAmplLst.append(oTerm.GetAttribute("m:u"))
                VoltAngLst.append(oTerm.GetAttribute("m:phiu"))
            else:
                VoltAmplLst.append(0)
                VoltAngLst.append(0)


    return(TermNameLst, VoltAmplLst, VoltAngLst)

def GetGenPower(sGen):
    '''
    This function retrieves the active and reactive power from generators.
    '''

    assert(type(sGen) == list), "Argument 'sGen' is not of type list"
    for i in range(len(sGen)):
        assert(type(sGen[i]) == pf.DataObject), "Argument 'sGen["+str(i)+"]' is not of type powerfactory.DataObject"

    GenNameLst = []
    ActPowLst = []
    ReactPowLst = []
    for oGen in sGen:
        if oGen.GetAttribute("for_name"):
            GenName = oGen.GetAttribute("for_name").replace("_","")
            GenName = ExtractForName(GenName)
            GenNameLst.append(oGen.GetAttribute("for_name").replace("_",""))
        else:
            GenNameLst.append(oGen.GetAttribute("loc_name").replace("_",""))
        if oGen.GetAttribute("outserv") == 1:
            ActPowLst.append(0)
            ReactPowLst.append(0)
        else:
            ActPowLst.append(oGen.GetAttribute("m:Psum:bus1"))
            ReactPowLst.append(oGen.GetAttribute("m:Qsum:bus1"))

    return(GenNameLst, ActPowLst, ReactPowLst)

def GetGenPowerSLO(sGen):
    '''
    This function retrieves the active and reactive power from generators.
    '''

    assert(type(sGen) == list), "Argument 'sGen' is not of type list"
    for i in range(len(sGen)):
        assert(type(sGen[i]) == pf.DataObject), "Argument 'sGen["+str(i)+"]' is not of type powerfactory.DataObject"

    GenNameLst = []
    ActPowLst = []
    ReactPowLst = []
    for oGen in sGen:
        if isElmInSLO(oGen):
            if oGen.GetAttribute("for_name"):
                GenTermName = oGen.GetAttribute("for_name").replace("_","")
                GenTermName = ExtractForName(GenTermName)
            else:
                GenTermName = oGen.GetAttribute("loc_name").replace("_","")
        else:
            GenTerm = getElmBus(oGen)
            GenTermName = GenTerm.GetAttribute("loc_name").replace("_","")
            GenTermName = returnAfterChar(GenTermName, " ")
        GenTermName = "Gen"+GenTermName
        if GenTermName in GenNameLst:
            n_entry = getNOfLstEntrys(GenNameLst, GenTermName)
            GenNameLst.append(GenTermName+str(n_entry))
        else:
            GenNameLst.append(GenTermName)
        if oGen.GetAttribute("outserv") == 1:
            ActPowLst.append(0)
            ReactPowLst.append(0)
        else:
            ActPowLst.append(oGen.GetAttribute("m:Psum:bus1"))
            ReactPowLst.append(oGen.GetAttribute("m:Qsum:bus1"))

    return(GenNameLst, ActPowLst, ReactPowLst)

def GetLodPower(sLod):
    '''
    This function retrieves the active and reactive power from loads.
    '''

    assert(type(sLod) == list), "Argument 'sLod' is not of type list"
    for i in range(len(sLod)):
        assert(type(sLod[i]) == pf.DataObject), "Argument 'sLod["+str(i)+"]' is not of type powerfactory.DataObject"

    LodNameLst = []
    ActPowLst = []
    ReactPowLst =[]
    for oLod in sLod:
        if oLod.GetAttribute("for_name"):
            LneName = oLod.GetAttribute("for_name").replace("_","")
            LneName = ExtractForName(LneName)
            LodNameLst.append(LneName)
        else:
            LodNameLst.append(oLod.GetAttribute("loc_name").replace("_",""))
        if oLod.GetAttribute("outserv") == 1:
            ActPowLst.append(0)
            ReactPowLst.append(0)
        else:
            ActPowLst.append(oLod.GetAttribute("m:Psum:bus1"))
            ReactPowLst.append(oLod.GetAttribute("m:Qsum:bus1"))

    return(LodNameLst, ActPowLst, ReactPowLst)

def GetLodPowerSLO(sLod):
    '''
    This function retrieves the active and reactive power from loads.
    '''

    assert(type(sLod) == list), "Argument 'sLod' is not of type list"
    for i in range(len(sLod)):
        assert(type(sLod[i]) == pf.DataObject), "Argument 'sLod["+str(i)+"]' is not of type powerfactory.DataObject"

    LodNameLst = []
    ActPowLst = []
    ReactPowLst =[]
    for oLod in sLod:
        if isElmInSLO(oLod):
            if oLod.GetAttribute("for_name"):
                LodTermName = oLod.GetAttribute("for_name").replace("_","")
                LodTermName = ExtractForName(LodTermName)
            else:
                LodTermName = oLod.GetAttribute("loc_name").replace("_","")
        else:
            LodTerm = getElmBus(oLod)
            LodTermName = LodTerm.GetAttribute("loc_name").replace("_","")
            LodTermName = returnAfterChar(LodTermName, " ")
        LodTermName = "Lod"+LodTermName
        if LodTermName in LodNameLst:
            n_entry =  getNOfLstEntrys(LodNameLst, LodTermName)
            LodNameLst.append(LodTermName+str(n_entry))
        else:
            LodNameLst.append(LodTermName)

        if oLod.GetAttribute("outserv") == 1:
            ActPowLst.append(0)
            ReactPowLst.append(0)
        else:
            ActPowLst.append(oLod.GetAttribute("m:Psum:bus1"))
            ReactPowLst.append(oLod.GetAttribute("m:Qsum:bus1"))

    return(LodNameLst, ActPowLst, ReactPowLst)

def GetLineTopology(sLines):
    '''
    This function retrieves wheter a line is operational or not.
    '''

    assert(type(sLines) == list), "Argument 'sLines' is not of type list"
    for i in range(len(sLines)):
        assert(type(sLines[i]) == pf.DataObject), "Argument 'sLines["+str(i)+"]' is not of type powerfactory.DataObject"

    LneNameLst = []
    LneStatusLst = []
    for oLne in sLines:
        bus1Status = 1
        bus2Status = 1
        for bus1Elm in oLne.GetAttribute("bus1").GetContents():
            if bus1Elm.GetAttribute("on_off") == 0:
                bus1Status = 0
        for bus2Elm in oLne.GetAttribute("bus2").GetContents():
            if bus2Elm.GetAttribute("on_off") == 0:
                bus2Status = 0

        if oLne.GetAttribute("for_name"):
            LneName = oLne.GetAttribute("for_name").replace("_","")
            LneName = ExtractForName(LneName)
            LneNameLst.append(oLne.GetAttribute("for_name").replace("_",""))
        else:
            LneNameLst.append(oLne.GetAttribute("loc_name").replace("_",""))

        if oLne.GetAttribute("outserv") == 1:
            LneStatusLst.append(0)
        elif bus1Status == 0:
            LneStatusLst.append(0)
        elif bus2Status == 0:
            LneStatusLst.append(0)
        else:
            LneStatusLst.append(1)

    return(LneNameLst, LneStatusLst)

def GetLineTopologySLO(sLines):
    '''
    This function retrieves wheter a line is operational or not.
    '''

    assert(type(sLines) == list), "Argument 'sLines' is not of type list"
    for i in range(len(sLines)):
        assert(type(sLines[i]) == pf.DataObject), "Argument 'sLines["+str(i)+"]' is not of type powerfactory.DataObject"

    LneNameLst = []
    LneStatusLst = []
    for oLne in sLines:
        bus1Status = 1
        bus2Status = 1
        if oLne.GetAttribute("bus1"):
            for bus1Elm in oLne.GetAttribute("bus1").GetContents():
                if bus1Elm.GetAttribute("on_off") == 0:
                    bus1Status = 0
        else:
            bus1Status = 0
        if oLne.GetAttribute("bus2"):
            for bus2Elm in oLne.GetAttribute("bus2").GetContents():
                if bus2Elm.GetAttribute("on_off") == 0:
                    bus2Status = 0
        else:
            bus2Status = 0
        if isElmInSLO(oLne):
            if oLne.GetAttribute("for_name"):
                LneName = oLne.GetAttribute("for_name").replace("_","")
                LneName = ExtractForName(LneName)
            else:
                LneName = oLne.GetAttribute("loc_name").replace("_","")
        else:
            oBus1 = getLneBus1(oLne)
            oBus2 = getLneBus2(oLne)
            if oBus1:
                Bus1Name = oBus1.GetAttribute("loc_name").replace("_","")
            else:
                Bus1Name = "None"
            if oBus2:
                Bus2Name = oBus2.GetAttribute("loc_name").replace("_","")
            else:
                Bus2Name = "None"
            Bus1Name = returnAfterChar(Bus1Name, " ")
            Bus2Name = returnAfterChar(Bus2Name, " ")
            LneName = Bus1Name+"-"+Bus2Name
        LneName = "Lne"+LneName
        if LneName in LneNameLst:
            n_entry = getNOfLstEntrys(LneNameLst,LneName)
            LneNameLst.append(LneName+str(n_entry))
        else:
            LneNameLst.append(LneName)

        if oLne.GetAttribute("outserv") == 1:
            LneStatusLst.append(0)
        elif bus1Status == 0:
            LneStatusLst.append(0)
        elif bus2Status == 0:
            LneStatusLst.append(0)
        else:
            LneStatusLst.append(1)

    return(LneNameLst, LneStatusLst)

def GetGenTopology(sGen):
    '''
    This function retrieves wheter a generator is operation or not 
    '''

    assert(type(sGen) == list), "Argument 'sGen' is not of type list"
    for i in range(len(sGen)):
        assert(type(sGen[i]) == pf.DataObject), "Argument 'sGen["+str(i)+"]' is not of type powerfactory.DataObject"

    GenNameLst = []
    GenStatusLst = []
    for oGen in sGen:
        bus1status = 1
        for Bus1Elm in oGen.GetAttribute("bus1").GetContents():
            if Bus1Elm.GetAttribute("on_off") == 0:
                bus1status = 0
        if oGen.GetAttribute("for_name"):
            GenName = oGen.GetAttribute("for_name").replace("_","")
            GenName = ExtractForName(GenName)
            GenNameLst.append(oGen.GetAttribute("for_name").replace("_",""))
        else:
            GenNameLst.append(oGen.GetAttribute("loc_name").replace("_",""))

        if oGen.GetAttribute("outserv") == 1:
            GenStatusLst.append(0)
        elif bus1status == 0:
            GenStatusLst.append(0)
        else:
            GenStatusLst.append(1)
            
    return(GenNameLst, GenStatusLst)

def GetGenTopologySLO(sGen):
    '''
    This function retrieves wheter a generator is operation or not 
    '''

    assert(type(sGen) == list), "Argument 'sGen' is not of type list"
    for i in range(len(sGen)):
        assert(type(sGen[i]) == pf.DataObject), "Argument 'sGen["+str(i)+"]' is not of type powerfactory.DataObject"

    GenNameLst = []
    GenStatusLst = []
    for oGen in sGen:
        bus1status = 1
        for Bus1Elm in oGen.GetAttribute("bus1").GetContents():
            if Bus1Elm.GetAttribute("on_off") == 0:
                bus1status = 0
    
        if isElmInSLO(oGen):
            if oGen.GetAttribute("for_name"):
                GenTermName = oGen.GetAttribute("for_name").replace("_","")
                GenTermName = ExtractForName(GenTermName)
            else:
                GenTermName = oGen.GetAttribute("loc_name").replace("_","")
        else:
            GenTerm = getElmBus(oGen)
            GenTermName = GenTerm.GetAttribute("loc_name").replace("_","")
            GenTermName = returnAfterChar(GenTermName, " ")
        GenTermName = "Gen"+GenTermName
        if GenTermName in GenNameLst:
            n_entry = getNOfLstEntrys(GenNameLst, GenTermName)
            GenNameLst.append(GenTermName+str(n_entry))
        else:
            GenNameLst.append(GenTermName)

        if oGen.GetAttribute("outserv") == 1:
            GenStatusLst.append(0)
        elif bus1status == 0:
            GenStatusLst.append(0)
        else:
            GenStatusLst.append(1)
            
    return(GenNameLst, GenStatusLst)

def GetLineFlowsSLO(sLne):
    '''
    This function retrieves the active and reactive powers of lines
    '''

    assert(type(sLne) == list), "Argument 'sLne' is not of type list"
    for i in range(len(sLne)):
        assert(type(sLne[i]) == pf.DataObject), "Argument 'sLne["+str(i)+"]' is not of type powerfactory.DataObject"

    LneNameList = []
    LneBus1PList = []
    LneBus1QList = []
    LneBus2PList = []
    LneBus2QList = []

    for oLne in sLne:
        if isElmInSLO(oLne):
            if oLne.GetAttribute("for_name"):
                LneName = oLne.GetAttribute("for_name").replace("_","")
                LneName = ExtractForName(LneName)
            else:
                LneName = oLne.GetAttribute("loc_name").replace("_","")
            LneName = "Lne"+LneName
            if LneName in LneNameList:
                n_entry = getNOfLstEntrys(LneNameList, LneName)
                LneNameList.append(LneName+str(n_entry))
            else:
                LneNameList.append(LneName)
            if oLne.GetAttribute("outserv") == 1:
                LneBus1PList.append(0)
                LneBus1QList.append(0)
                LneBus2PList.append(0)
                LneBus2QList.append(0)
            else:
                LneBus1PList.append(oLne.GetAttribute("m:P:bus1"))
                LneBus1QList.append(oLne.GetAttribute("m:Q:bus1"))
                LneBus2PList.append(oLne.GetAttribute("m:P:bus2"))
                LneBus2QList.append(oLne.GetAttribute("m:Q:bus2"))
            
    return(LneNameList, LneBus1PList, LneBus1QList, LneBus2PList, LneBus2QList)

def GetTermShc(sTerm):
    '''
    This function retrieves the short circuit powers of terminals
    '''
    assert(type(sTerm) == list), "Argument 'sTerm' is not of type list"
    for i in range(len(sTerm)):
        assert(type(sTerm[i]) == pf.DataObject), "Argument 'oTerm["+str(i)+"]' is not of type powerfactory.DataObject"
    
    TermNameLst = []
    TermShcLst = []
    for oTerm in sTerm:
        if oTerm.GetAttribute("iUsage") == 0:
            if oTerm.cpSubstat:
                SubstatName = oTerm.GetAttribute("cpSubstat").GetAttribute("loc_name").replace("_","")
                TermName = oTerm.GetAttribute("loc_name").replace("_","")
                TermNameLst.append(SubstatName+"_"+TermName)
            else:
                TermName = oTerm.GetAttribute("loc_name").replace("_","")
                TermNameLst.append(TermName)
            
            if oTerm.GetAttribute("outserv") == 0:
                TermShcLst.append(oTerm.GetAttribute("m:Skss"))
            else:
                TermShcLst.append(0)

    return(TermNameLst, TermShcLst)

def GetTermShcSLO(sTerm):
    '''
    This function retrieves the short circuit powers of terminals
    '''
    assert(type(sTerm) == list), "Argument 'sTerm' is not of type list"
    for i in range(len(sTerm)):
        assert(type(sTerm[i]) == pf.DataObject), "Argument 'oTerm["+str(i)+"]' is not of type powerfactory.DataObject"
    
    TermNameLst = []
    TermShcLst = []
    for oTerm in sTerm:
        if oTerm.GetAttribute("iUsage") == 0:
            if oTerm.GetAttribute("for_name"):
                TermName = oTerm.GetAttribute("for_name").replace("_","")
                TermName = ExtractForName(TermName)
            else:
                if oTerm.cpSubstat:
                    SubstatName = oTerm.GetAttribute("cpSubstat").GetAttribute("loc_name").replace("_","")
                    TermName = oTerm.GetAttribute("loc_name").replace("_","")
                    TermName = SubstatName+"\\"+TermName
                else:
                    TermName = oTerm.GetAttribute("loc_name").replace("_","")
                    TermName = returnAfterChar(TermName, " ")
            TermName = "Bus"+TermName
            if TermName in TermNameLst:
                n_entry = getNOfLstEntrys(TermNameLst, TermName)
                TermNameLst.append(TermName+str(n_entry))
            else:
                TermNameLst.append(TermName)
            
            if oTerm.GetAttribute("outserv") == 0:
                TermShcLst.append(oTerm.GetAttribute("m:Skss"))
            else:
                TermShcLst.append(0)

    return(TermNameLst, TermShcLst)


def setRefBus(app: pf.Application, oRefBus: pf.DataObject) -> bool:
    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application"
    assert(type(oRefBus) == pf.DataObject), "Argument 'oRefBus' is not of type powerfactory.DataObject"

    oComLdf = app.GetFromStudyCase("ComLdf")
    oComLdf.SetAttribute("rembar", oRefBus)
    oComLdf.SetAttribute("phiini",150)