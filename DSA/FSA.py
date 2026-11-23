'''
Author: Matjaz Skrlec
date: 11. 10. 2024
version: 1.0
description: This module is used for Frequancy stability assessment using powerfactory.
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import DSA.LFDD as LFDD
import PFSupport.Utils
import DSA.HandleFiles as HandleFiles
import sys
import tqdm
import logging
from collections.abc import Iterable

# support functions
def ExtractForName(ForName: str):
    forIndex = ForName.find(":")
    if forIndex:
        ForName = ForName[forIndex+1:]
    return ForName

def getForOrLocName(oElm) -> str:
    match type(oElm):
        case pf.DataObject:
            if oElm.GetAttribute("for_name"):
                oElmName = oElm.GetAttribute("for_name")
                oElmName = ExtractForName(oElmName)
                return oElmName
            else:
                return oElm.GetAttribute("loc_name")
        case int:
            return(oElm)
        
def GetdtUnitModifier(oComInc):
    UnitDict = {"as": 1e18,
                "fs": 1e15,
                "ps": 1e12,
                "ns": 1e9,
                "us": 1e6,
                "ms": 1e3,
                "s": 1,
                "ks": 1e-3,
                "Ms": 1e-6,
                "Gs": 1e-9,
                "Ts": 1e-12,
                "Ps": 1e-15,
                "Es": 1e-18}
    dtUnit = oComInc.GetAttributeUnit('dtgrd')
    return(UnitDict[dtUnit])

def setUserParamas(oComInc: pf.DataObject, oComSim: pf.DataObject, tStartFSA: float, tStopFSA: float, tSimStepFSA: float) -> tuple[int, int, float, float, float, int]:
    '''
    This function sets the parameters of the simulation during frequency stability assessment and returns the initial settings.
    '''

    assert(type(oComInc) == pf.DataObject), "Argument 'oComInc' is not of type powerfactory.DataObject"
    assert(oComInc.GetClassName() == "ComInc"), "Argument 'oComInc' is not a initial conditions command"
    assert(type(oComSim) == pf.DataObject), "Argument 'oComSim' is not of type powerfactory.DataObject"
    assert(oComSim.GetClassName() == "ComSim"), "Argument 'oComSim' is not a simulation command"

    assert(type(tStartFSA) in [int, float]), "Argument 'tStartFSA' is not of type int or float"
    assert(type(tStopFSA) in [int, float]), "Argument 'tStopFSA' is not of type int or float"
    assert(type(tSimStepFSA) in [int, float]), "Argument 'tSimStepFSA' is not of type int or float"

    assert(tStartFSA <= 0), "Simulation start time ('tStartFSA') should be lower or equal to 0"
    assert(tStopFSA > tStartFSA), "Simulation stop time ('tStopFSA') has to be higher than simulation start time"

    # get modifier for dt
    dtModifier = GetdtUnitModifier(oComInc)

    # Get initial simulation setup
    SimInitSetup = (oComInc.iopt_simscn, oComInc.iopt_sample, oComInc.tstart, oComSim.tstop, oComInc.dtgrd, oComInc.automaticCompilation)

    oComInc.iopt_simscn = 0
    oComInc.iopt_sample = 0
    oComInc.tstart = tStartFSA
    oComSim.tstop = tStopFSA
    oComInc.dtgrd = tSimStepFSA*dtModifier
    oComInc.automaticCompilation = 0

    return(SimInitSetup)

def setInitialParams(oComInc: pf.DataObject, oComSim: pf.DataObject, SimInitSetup: tuple[int, int, float, float, float, int]) -> None:
    '''
    This function sets the initial parameters of the simulation during frequency stability assessment.
    '''

    assert(type(oComInc) == pf.DataObject), "Argument 'oComInc' is not of type powerfactory.DataObject"
    assert(oComInc.GetClassName() == "ComInc"), "Argument 'oComInc' is not a initial conditions command"
    assert(type(oComSim) == pf.DataObject), "Argument 'oComSim' is not of type powerfactory.DataObject"
    assert(oComSim.GetClassName() == "ComSim"), "Argument 'oComsim' is not a simulation command"

    assert(type(SimInitSetup) == tuple), "Argument 'SimInitSetup' is not of type tuple"
    assert(len(SimInitSetup) == 6), "Argument 'SimInitsetup' does not have 5 entrys"

    assert(type(SimInitSetup[0]) == int), "Argument 'SimInitSetup[0]' is not ot type int"
    assert(type(SimInitSetup[1]) == int), "Argument 'SimInitSetup[1]' is not ot type int"
    assert(type(SimInitSetup[2]) in [int, float]), "Argument 'SimInitSetup[2]' is not of type int or float"
    assert(type(SimInitSetup[3]) in [int, float]), "Argument 'SimInitSetup[3]' is not of type int or float"
    assert(type(SimInitSetup[4]) in [int, float]), "Argument 'SimInitSetup[4]' is not of type int or float"

    oComInc.iopt_simscn = SimInitSetup[0]
    oComInc.iopt_sample = SimInitSetup[1]
    oComInc.tstart = SimInitSetup[2]
    oComSim.tstop = SimInitSetup[3]
    oComInc.dtgrd = SimInitSetup[4]
    oComInc.automaticCompilation = SimInitSetup[5]

def setFSAEvents(oComInc: pf.DataObject) -> tuple[pf.DataObject, list[tuple[pf.DataObject, int]]]:
    '''
    This function disables all events setup previous to Frequency stability assessment and saves the previoud setups.
    It also creates a generator outage event.
    '''
    assert(type(oComInc) == pf.DataObject), "Argument 'oComInc' is not of type powerfactory.DataObject"
    assert(oComInc.GetClassName() == "ComInc"), "Argument 'oComInc' is not a initial conditions command"

    # put the original events out of service and store the original value of the event
    EvtInitSetup = []
    oEvent = oComInc.p_event
    sEvents = oEvent.GetContents()
    for oEvt in sEvents:
        EvtInitSetup.append((oEvt,oEvt.GetAttribute("outserv")))
        oEvt.SetAttribute("outserv", 1)

    # add gen outage
    oGenOutEvt = oEvent.CreateObject("EvtOutage", "Generator_outage")

    oGenOutEvt.SetAttribute("outserv", 0)
    oGenOutEvt.SetAttribute("time", 1)
    oGenOutEvt.SetAttribute("i_what", 3)

    return(oGenOutEvt, EvtInitSetup)

def setInitialEvents(oGenOutEvt: pf.DataObject, initUserEvents: tuple[pf.DataObject, list[tuple[pf.DataObject, int]]]) -> bool:
    '''
    This function set up the initial events as they were before the frequency stability assessment
    '''
    assert(type(oGenOutEvt) == pf.DataObject), "Argument 'oGetOutEvt' is not of type powerfactory.DataObject"
    assert(type(initUserEvents) == list), "Argument 'initUserEvents' is not of type list"

    oGenOutEvt.Delete()

    for oEvt in initUserEvents:
        oEvt[0].SetAttribute("outserv", oEvt[1])

    return (True)

def CheckIfDSLTypExists(name: str, folder: pf.DataObject, iprint: bool) -> tuple[bool, pf.DataObject]:
    '''
    This function checks if a DSL type element with the given name already exist in the given folder.
    '''

    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(folder) == pf.DataObject), "Argument 'folder' is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument 'folder' is not of class IntPrjfolder or IntFolder"
    assert(type(iprint) == bool), "Argument 'iprint' is not of type bool"

    for i in folder.GetContents():
        if i.loc_name == name:
            if iprint:
                print("Type object with the name %s in folder %s already exists." % (name, folder.GetAttribute("loc_name")))
                logging.info("Type object with the name %s in folder %s already exists." % (name, folder.GetAttribute("loc_name")))
            return(True, i)
    if iprint:
        print("Type object with the name %s does not exist in folder %s." % (name, folder.GetAttribute("loc_name")))
        logging.info("Type object with the name %s does not exist in folder %s." % (name, folder.GetAttribute("loc_name")))
    return(False, 0)

def CheckIfDSLElmExists(name: str, grid: pf.DataObject, iprint: bool) -> tuple[bool, pf.DataObject]:
    '''
    This function checks if a DSL element with the given name already exists in the given grid.
    '''
    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(grid) == pf.DataObject), "Argument 'grid' is not of type powerfactory.DataObject"
    assert(grid.GetClassName() in ["ElmNet", "IntFolder"]), "Argument 'grid' is not of class 'ElmNet' or 'IntFolder'"
    assert(type(iprint) == bool), "Argument 'iprint' is not of type bool"

    for i in grid.GetContents():
        if i.loc_name == name:
            if iprint:
                print("Element with the name %s in grid %s already exists." % (name, grid.GetAttribute("loc_name")))
                logging.info("Element with the name %s in grid %s already exists." % (name, grid.GetAttribute("loc_name")))
            return(True, i)
    if iprint:
        print("Element with the name %s does not exist in grid %s." % (name, grid.GetAttribute("loc_name")))
        logging.info("Element with the name %s does not exist in grid %s." % (name, grid.GetAttribute("loc_name")))
    return(False, 0)

def CreateRoCoFBlkType(name: str, folder: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a block type which calculates the rate of change of frequency
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type with name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type with name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    # equation_list = ["inc(f_iprev) = 0",\
    #                  "inc(RoCoF) = 0",\
    #                  "f_iprev = delay(freq, 0.01)",\
    #                  "RoCoF = (freq-f_iprev)/0.01"]

    equation_list = ["inc(x) = 1",\
                     "inc(f_iprev) = 0",\
                     "inc(yo) = 0",\
                     "inc(RoCoF) = 0",\
                     "dx = (freq-x)/0.01",\
                     "x.= dx",\
                     "yo = dx",\
                     "RoCoF = movingavg(yo, 0, 0.5)"]

    RoCoFBlkTyp = folder.CreateObject("BlkDef", name)
    RoCoFBlkTyp.SetAttribute("sInput", ["freq"])
    RoCoFBlkTyp.SetAttribute("sOutput", ["RoCoF"])
    RoCoFBlkTyp.SetAttribute("sStates", ["x"])
    RoCoFBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(RoCoFBlkTyp)

def CreateRoCoFBlkType2(name: str, folder: pf.DataObject, delay: float, timestep = float) -> pf.DataObject:
    '''
    This function creates a block type which calculates the rate of change of frequency
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"
    assert(isinstance(delay, (int, float))), "Argument delay is not a number"
    assert(isinstance(timestep, (int, float))), "Argumnet timestep is not a number"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type with name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type with name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    if delay < timestep:
        equation_list = ["inc(f_iprev) = 0",\
                        "inc(RoCoF) = 0",\
                        f"f_iprev = delay(freq, {timestep})",\
                        f"RoCoF = (freq-f_iprev)/{timestep}"]

        RoCoFBlkTyp = folder.CreateObject("BlkDef", name)
        RoCoFBlkTyp.SetAttribute("sInput", ["freq"])
        RoCoFBlkTyp.SetAttribute("sOutput", ["RoCoF"])
        RoCoFBlkTyp.SetAttribute("sAddEquat", equation_list)
        
    else:
        equation_list = ["inc(x) = 1",\
                        "inc(f_iprev) = 0",\
                        "inc(yo) = 0",\
                        "inc(RoCoF) = 0",\
                        f"dx = (freq-x)/{timestep}",\
                        "x.= dx",\
                        "yo = dx",\
                        f"RoCoF = movingavg(yo, 0, {delay})"]

        RoCoFBlkTyp = folder.CreateObject("BlkDef", name)
        RoCoFBlkTyp.SetAttribute("sInput", ["freq"])
        RoCoFBlkTyp.SetAttribute("sOutput", ["RoCoF"])
        RoCoFBlkTyp.SetAttribute("sStates", ["x"])
        RoCoFBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(RoCoFBlkTyp)

def CreateMBlkType(name: str, folder: pf.DataObject, freqLim: float) -> pf.DataObject:
    '''
    This function creates a block type, which calculater the M factor
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"
    assert(type(freqLim) in [int, float]), "Argument freqLim is not of type int or float"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    equation_list = ["inc(M) = 100",\
                     "M_init = ("+str(freqLim)+" - Freq)/RoCoF",\
                     "M_relevant = select(RoCoF > -0.001, 100, M_init)",\
                     "M_inter = select(M_relevant > 100, 100, M_relevant)",\
                     "M = select(M_inter < 0, 100, M_inter)"]

    MBlkTyp = folder.CreateObject("BlkDef", name)
    MBlkTyp.SetAttribute("sInput", ["RoCoF, Freq"])
    MBlkTyp.SetAttribute("sOutput", ["M"])
    MBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(MBlkTyp)

def CreatefMinBlkType(name: str, folder: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a block type, that monitors the minimum frequency during the simulation 
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    equation_list = ["inc(min_freq) = 2",\
                     "inc(min_freq_delay) = 2",\
                     "min_freq_delay = delay(min_freq, 0.001)", \
                     "min_freq = select(freq < min_freq_delay, freq, min_freq_delay)"]

    minFBlkTyp = folder.CreateObject("BlkDef", name)
    minFBlkTyp.SetAttribute("sInput", ["freq"])
    minFBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(minFBlkTyp)

def CreatefMaxBlkType(name: str, folder):
    '''
    This function creates a block type, that monitors the maximum frequency during the simulation 
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    equation_list = ["inc(max_freq) = 0",\
                     "inc(max_freq_delay) = 0",\
                     "max_freq_delay = delay(max_freq, 0.001)", \
                     "max_freq = select(freq > max_freq_delay, freq, max_freq_delay)"]

    maxFBlkTyp = folder.CreateObject("BlkDef", name)
    maxFBlkTyp.SetAttribute("sInput", ["freq"])
    maxFBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(maxFBlkTyp)

def CreateRoCoFMaxBlkType(name: str, folder: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a block type, that monitors the absolute maximum rate of change of frequency during the simulation 
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    equation_list = ["inc(max_RoCoF) = 0",\
                     "inc(max_RoCoF_delay) = 0",\
                     "abs_RoCoF = abs(RoCoF)",\
                     "max_RoCoF_delay = delay(max_RoCoF, 0.01)", \
                     "max_RoCoF = select(abs_RoCoF > max_RoCoF_delay, abs_RoCoF, max_RoCoF_delay)"]

    maxRoCoFBlkTyp = folder.CreateObject("BlkDef", name)
    maxRoCoFBlkTyp.SetAttribute("sInput", ["RoCoF"])
    maxRoCoFBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(maxRoCoFBlkTyp)

def CreateMinMBlkType(name: str, folder: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a block type, which monitors the minimum M value during the simulation
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of class IntPrjfolder or IntFolder"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        logging.info(f"Given DSL type name {name} already exists in given foler, not creating new DSL type")
        return(typ)

    equation_list = ["inc(M) = 100",\
                     "inc(min_M) = 100",\
                     "inc(min_M_delay) = 100",\
                     "min_M_delay = delay(min_M, 0.001)",\
                     "min_M = select(M < min_M_delay, M, min_M_delay)"]

    minMBlkTyp = folder.CreateObject("BlkDef", name)
    minMBlkTyp.SetAttribute("sInput", ["M"])
    minMBlkTyp.SetAttribute("sAddEquat", equation_list)
    
    return(minMBlkTyp)

def CreateMCompBlkTyp(name: str, folder: pf.DataObject, freqLimLst: tuple) -> tuple[pf.DataObject, pf.DataObject, pf.DataObject, pf.DataObject, pf.DataObject, list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates the composite model for M calculation.
    '''
    
    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjFolder", "IntFolder"]), "Argument foler is not of class 'IntFolder' or 'IntPrjfolder'"
    assert(type(freqLimLst) == tuple), "Argument freqLim is not of type int or float"

    exist_bool, ComTyp = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given folder, not creating new DSL Type")
        logging.info(f"Given DSL type name {name} already exists in given folder, not creating new DSL Type")
        return (ComTyp)

    CompBlkTyp = folder.CreateObject("BlkDef", name)
    RoCoFBlkTyp = CreateRoCoFBlkType("RoCoF", folder)
    minFBlkTyp = CreatefMinBlkType("fMin",folder)
    maxFBlkTyp = CreatefMaxBlkType("fMax",folder)
    maxRoCoFBlkTyp = CreateRoCoFMaxBlkType("RoCoFMax",folder)

    MBlkTypLst = []
    MinMBlkTypLst = []
    for freqLim in freqLimLst:
        CurrMBlkTyp = CreateMBlkType("M_"+str(freqLim), folder, freqLim)
        MBlkTypLst.append(CurrMBlkTyp)

    for freqLim in freqLimLst:
        CurrMinMBlkTyp = CreateMinMBlkType("minM_"+str(freqLim), folder)
        MinMBlkTypLst.append(CurrMinMBlkTyp)


    FreqSlot = CompBlkTyp.CreateObject("BlkSlot", "FreqMeas")
    FreqSlot.SetAttribute("sOutput", ["fe"])
    RoCoFSlot = CompBlkTyp.CreateObject("BlkSlot", "RoCoF")
    RoCoFSlot.SetAttribute("pDsl", RoCoFBlkTyp)
    minFSlot = CompBlkTyp.CreateObject("BlkSlot", "minF")
    minFSlot.SetAttribute("pDsl", minFBlkTyp)
    maxFSlot = CompBlkTyp.CreateObject("BlkSlot", "maxF")
    maxFSlot.SetAttribute("pDsl", maxFBlkTyp)
    maxRoCoFSlot = CompBlkTyp.CreateObject("BlkSlot", "maxRoCoF")
    maxRoCoFSlot.SetAttribute("pDsl", maxRoCoFBlkTyp)
    
    MSlotLst = []
    minMSlotLst = []
    for i in range(len(MBlkTypLst)):
        currMSlt = CompBlkTyp.CreateObject("BlkSlot","M_"+str(i+1))
        currMSlt.SetAttribute("pDsl", MBlkTypLst[i])
        MSlotLst.append(currMSlt)

    for i in range(len(MinMBlkTypLst)):
        currMinMSlt = CompBlkTyp.CreateObject("BlkSlot", "minM_"+str(i+1))
        currMinMSlt.SetAttribute("pDsl", MinMBlkTypLst[i])
        minMSlotLst.append(currMinMSlt)

    freqSig1 = CompBlkTyp.CreateObject("BlkSig", "freq1")
    freqSig1.SetAttribute("pnodfrom", FreqSlot)
    freqSig1.SetAttribute("inodfrom", 0)
    freqSig1.SetAttribute("pnodto", RoCoFSlot)
    freqSig1.SetAttribute("iconto", 1)
    freqSig1.SetAttribute("inodto", 0)

    freqSig = CompBlkTyp.CreateObject("BlkSig", "freq")
    freqSig.SetAttribute("pnodfrom", FreqSlot)
    freqSig.SetAttribute("inodfrom", 0)
    freqSig.SetAttribute("pnodto", minFSlot)
    freqSig.SetAttribute("iconto", 1)
    freqSig.SetAttribute("inodto", 0)

    freqSig = CompBlkTyp.CreateObject("BlkSig", "freq")
    freqSig.SetAttribute("pnodfrom", FreqSlot)
    freqSig.SetAttribute("inodfrom", 0)
    freqSig.SetAttribute("pnodto", maxFSlot)
    freqSig.SetAttribute("iconto", 1)
    freqSig.SetAttribute("inodto", 0)

    RoCoFSig = CompBlkTyp.CreateObject("BlkSig", "RoCoF")
    RoCoFSig.SetAttribute("pnodfrom", RoCoFSlot)
    RoCoFSig.SetAttribute("inodfrom", 0)
    RoCoFSig.SetAttribute("pnodto", maxRoCoFSlot)
    RoCoFSig.SetAttribute("iconto", 1)
    RoCoFSig.SetAttribute("inodto", 0)

    for MSlot in MSlotLst:
        freqSig = CompBlkTyp.CreateObject("BlkSig", "freq2")
        freqSig.SetAttribute("pnodfrom", FreqSlot)
        freqSig.SetAttribute("inodfrom", 0)
        freqSig.SetAttribute("pnodto", MSlot)
        freqSig.SetAttribute("iconto", 1)
        freqSig.SetAttribute("inodto", 1)

        RoCoFSig = CompBlkTyp.CreateObject("BlkSig", "RoCoF")
        RoCoFSig.SetAttribute("pnodfrom", RoCoFSlot)
        RoCoFSig.SetAttribute("inodfrom", 0)
        RoCoFSig.SetAttribute("pnodto", MSlot)
        RoCoFSig.SetAttribute("iconto", 1)
        RoCoFSig.SetAttribute("inodto", 0)

    for MSlot, minMSlot in zip(MSlotLst, minMSlotLst):
        MSig = CompBlkTyp.CreateObject("BlkSig", "M")
        MSig.SetAttribute("pnodfrom", MSlot)
        MSig.SetAttribute("inodfrom", 0)
        MSig.SetAttribute("pnodto", minMSlot)
        MSig.SetAttribute("iconto", 1)
        MSig.SetAttribute("inodto", 0)

    return (CompBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst)

def CreateRoCoFCompBlkTyp2(name: str, folder: pf.DataObject, RoCoFDelays: list, timestep: float) -> list[pf.DataObject]:
    '''
    This function creates the composite model for M calculation.
    '''
    
    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactory.DataObject"
    assert(folder.GetClassName() in ["IntPrjFolder", "IntFolder"]), "Argument foler is not of class 'IntFolder' or 'IntPrjfolder'"
    assert(isinstance(RoCoFDelays, Iterable)), "Argument 'RoCoFDelays' is not an Iterable"
    assert(isinstance(timestep, (int, float))), "Argument timestep is not a number"

    exist_bool, ComTyp = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        print(f"Given DSL type name {name} already exists in given folder, not creating new DSL Type")
        logging.info(f"Given DSL type name {name} already exists in given folder, not creating new DSL Type")
        return (ComTyp)

    CompBlkTyp = folder.CreateObject("BlkDef", name)
    minFBlkTyp = CreatefMinBlkType("fMin",folder)
    maxFBlkTyp = CreatefMaxBlkType("fMax",folder)
    RoCoFBlkTypList = []
    maxRoCoFBlkTypList = []
    for i, delay in enumerate(RoCoFDelays):
        RoCoFBlkTyp = CreateRoCoFBlkType2(f"RoCoF{i}", folder, delay, timestep)
        maxRoCoFBlkTyp = CreateRoCoFMaxBlkType(f"RoCoFMax{i}",folder)
        RoCoFBlkTypList.append(RoCoFBlkTyp)
        maxRoCoFBlkTypList.append(maxRoCoFBlkTyp)

    FreqSlot = CompBlkTyp.CreateObject("BlkSlot", "FreqMeas")
    FreqSlot.SetAttribute("sOutput", ["fe"])
    minFSlot = CompBlkTyp.CreateObject("BlkSlot", "minF")
    minFSlot.SetAttribute("pDsl", minFBlkTyp)
    maxFSlot = CompBlkTyp.CreateObject("BlkSlot", "maxF")
    maxFSlot.SetAttribute("pDsl", maxFBlkTyp)

    RoCoFSlotList = []
    maxRoCoFSlotList = []
    for i, currRoCoFBlkTyp in enumerate(RoCoFBlkTypList):
        RoCoFSlot = CompBlkTyp.CreateObject("BlkSlot", f"RoCoF{i}")
        RoCoFSlot.SetAttribute("pDsl", currRoCoFBlkTyp)
        RoCoFSlotList.append(RoCoFSlot)
    for i, currMaxRoCoFBlkTyp in enumerate(maxRoCoFBlkTypList):
        maxRoCoFSlot = CompBlkTyp.CreateObject("BlkSlot", f"maxRoCoF{i}")
        maxRoCoFSlot.SetAttribute("pDsl", currMaxRoCoFBlkTyp)
        maxRoCoFSlotList.append(maxRoCoFSlot)

    freqSig = CompBlkTyp.CreateObject("BlkSig", "freq")
    freqSig.SetAttribute("pnodfrom", FreqSlot)
    freqSig.SetAttribute("inodfrom", 0)
    freqSig.SetAttribute("pnodto", minFSlot)
    freqSig.SetAttribute("iconto", 1)
    freqSig.SetAttribute("inodto", 0)

    freqSig = CompBlkTyp.CreateObject("BlkSig", "freq")
    freqSig.SetAttribute("pnodfrom", FreqSlot)
    freqSig.SetAttribute("inodfrom", 0)
    freqSig.SetAttribute("pnodto", maxFSlot)
    freqSig.SetAttribute("iconto", 1)
    freqSig.SetAttribute("inodto", 0)
    
    for currRoCoFSlot, currmaxRoCoFSlot in zip(RoCoFSlotList, maxRoCoFSlotList):
        freqSig1 = CompBlkTyp.CreateObject("BlkSig", "freq1")
        freqSig1.SetAttribute("pnodfrom", FreqSlot)
        freqSig1.SetAttribute("inodfrom", 0)
        freqSig1.SetAttribute("pnodto", currRoCoFSlot)
        freqSig1.SetAttribute("iconto", 1)
        freqSig1.SetAttribute("inodto", 0)

        RoCoFSig = CompBlkTyp.CreateObject("BlkSig", "RoCoF")
        RoCoFSig.SetAttribute("pnodfrom", currRoCoFSlot)
        RoCoFSig.SetAttribute("inodfrom", 0)
        RoCoFSig.SetAttribute("pnodto", currmaxRoCoFSlot)
        RoCoFSig.SetAttribute("iconto", 1)
        RoCoFSig.SetAttribute("inodto", 0)

    return (CompBlkTyp, minFBlkTyp, maxFBlkTyp, RoCoFBlkTypList, maxRoCoFBlkTypList)

def CreateRoCoFBlkElm(name: str, CompModel: pf.DataObject, RoCoFBlkTyp: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a dynamic model element which calculates the rate of change of frequency
    '''

    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(CompModel) == pf.DataObject), "Argument 'CompModel' is not of type powerfactory.DataObject"
    assert(CompModel.GetClassName() == "ElmComp"), "Argument 'CompModel' is not of class 'ElmComp'"
    assert(type(RoCoFBlkTyp) == pf.DataObject), "Argument 'RoCoFBlkTyp' is not of type powerfactory.DataObject"
    assert(RoCoFBlkTyp.GetClassName() == "BlkDef"), "Argument 'RoCoFBlkType' is not of class 'BlkDef'"

    RoCoFBlkElm = CompModel.CreateObject("ElmDsl", name)
    RoCoFBlkElm.SetAttribute("typ_id", RoCoFBlkTyp)

    return(RoCoFBlkElm)

def CreateMBlkElm(name: str, CompModel: pf.DataObject, MBlkTyp: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a synamic model element which calculates the M value
    '''

    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(CompModel) == pf.DataObject), "Argument 'CompModel' is not of type powerfactory.DataObject"
    assert(CompModel.GetClassName() == "ElmComp"), "Argument 'CompModel' is not of class 'ElmComp'"
    assert(type(MBlkTyp) == pf.DataObject), "Argument 'MBlkTyp' is not of type powerfactory.DataObject"
    assert(MBlkTyp.GetClassName() == "BlkDef"), "Argument 'MBlkTyp' is not of class 'BlkDef'"

    MBlkElm = CompModel.CreateObject("ElmDsl", name)
    MBlkElm.SetAttribute("typ_id", MBlkTyp)

    return(MBlkElm)

def CreateMCompElm(name: str, CompBlkTyp: pf.DataObject, RoCoFBlkTyp: pf.DataObject, minFBlkTyp: pf.DataObject, maxFBlkTyp: pf.DataObject, maxRoCoFBlkTyp: pf.DataObject, MBlkTypLst: list[pf.DataObject], MinMBlkTypLst: list[pf.DataObject], Gen: pf.DataObject, grid: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a composite model element which calculates the rate of change of frequency and the M value of a generator
    '''

    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(CompBlkTyp) == pf.DataObject), "Argument 'CompBlkTyp' is not of type powerfactory.DataObject"
    assert(CompBlkTyp.GetClassName() == 'BlkDef'), "Argument 'CompBlkTyp' is not of class BlkDef"
    assert(type(RoCoFBlkTyp) == pf.DataObject), "Argument 'RoCoFBlkTyp' is not of type powerfactory.DataObject"
    assert(RoCoFBlkTyp.GetClassName() == 'BlkDef'), "Argument 'RoCoFBlkTyp' is not of class BlkDef"
    assert(type(minFBlkTyp) == pf.DataObject), "Argument 'minFBlkTyp' is not of type powerfactory.DataObject"
    assert(minFBlkTyp.GetClassName() == 'BlkDef'), "Argument 'minFBlkTyp' is not of class BlkDef"
    assert(type(maxFBlkTyp) == pf.DataObject), "Argument 'maxFBlkTyp' is not of type powerfactory.DataObject"
    assert(maxFBlkTyp.GetClassName() == 'BlkDef'), "Argument 'maxFBlkTyp' is not of class BlkDef"
    assert(type(maxRoCoFBlkTyp) == pf.DataObject), "Argument 'maxRoCoFBlkTyp' is not of type powerfactory.DataObject"
    assert(maxRoCoFBlkTyp.GetClassName() == 'BlkDef'), "Argument 'maxRoCoFBlkTyp' is not of class BlkDef"
    assert(type(MBlkTypLst) == list), "Argument 'MBlkTypLst' is not of type list"
    assert(type(MinMBlkTypLst) == list), "Argument 'MinMBlkTypLst' is not of type list"
    assert(type(Gen) == pf.DataObject), "Argument 'Gen' is not of type powerfactory.DataObject"
    assert(Gen.GetClassName() == "ElmSym"), "Argument 'ElmSym' is not of class 'ElmSym'"
    assert(type(grid) == pf.DataObject), "Argument 'grid' is not of type powerfactory.DataObject"
    assert(grid.GetClassName() in ["ElmNet", "IntFolder"]), "Argument 'grid' is not of class ElmNet or IntFolder"

    exist_bool, Com = CheckIfDSLElmExists(name, grid, False)

    if exist_bool:
        print(f"Given composite model element {name} already exists, not creating new one")
        logging.info(f"Given composite model element {name} already exists, not creating new one")
        return(Com)

    MCompElm = grid.CreateObject("ElmComp", name)
    MCompElm.SetAttribute("typ_id", CompBlkTyp)

    RoCoFBlkElm = MCompElm.CreateObject("ElmDsl", "RoCoF")
    RoCoFBlkElm.SetAttribute("typ_id", RoCoFBlkTyp)

    minFBlkElm = MCompElm.CreateObject("ElmDsl", "minF")
    minFBlkElm.SetAttribute("typ_id", minFBlkTyp)

    maxFBlkElm = MCompElm.CreateObject("ElmDsl", "maxF")
    maxFBlkElm.SetAttribute("typ_id", maxFBlkTyp)

    maxRoCoFBlkElm = MCompElm.CreateObject("ElmDsl", "maxRoCoF")
    maxRoCoFBlkElm.SetAttribute("typ_id", maxRoCoFBlkTyp)

    MBlkElmLst = []
    for i in range(len(MBlkTypLst)):
        MBlkElm = MCompElm.CreateObject("ElmDsl", "M_"+str(i+1))
        MBlkElm.SetAttribute("typ_id", MBlkTypLst[i])
        MBlkElmLst.append(MBlkElm)

    minMBlkElmLst = []
    for i in range(len(MinMBlkTypLst)):
        minMBlkElm = MCompElm.CreateObject("ElmDsl", "minM_"+str(i+1))
        minMBlkElm.SetAttribute("typ_id", MinMBlkTypLst[i])
        minMBlkElmLst.append(minMBlkElm)

    pelm_list = [Gen, RoCoFBlkElm, minFBlkElm, maxFBlkElm, maxRoCoFBlkElm]+MBlkElmLst+minMBlkElmLst

    MCompElm.SetAttribute("pelm", pelm_list)

    return(MCompElm)

def CreateRoCoFCompElm(name: str, CompBlkTyp: pf.DataObject, minFBlkTyp: pf.DataObject, maxFBlkTyp: pf.DataObject, RoCoFBlkTypList: list[pf.DataObject], maxRoCoFBlkTypList: list[pf.DataObject], Gen: pf.DataObject, grid: pf.DataObject) -> pf.DataObject:
    '''
    This function creates a composite model element which calculates the rate of change of frequency of a generator
    '''

    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(CompBlkTyp) == pf.DataObject), "Argument 'CompBlkTyp' is not of type powerfactory.DataObject"
    assert(CompBlkTyp.GetClassName() == 'BlkDef'), "Argument 'CompBlkTyp' is not of class BlkDef"
    assert(type(minFBlkTyp) == pf.DataObject), "Argument 'minFBlkTyp' is not of type powerfactory.DataObject"
    assert(minFBlkTyp.GetClassName() == 'BlkDef'), "Argument 'minFBlkTyp' is not of class BlkDef"
    assert(type(maxFBlkTyp) == pf.DataObject), "Argument 'maxFBlkTyp' is not of type powerfactory.DataObject"
    assert(maxFBlkTyp.GetClassName() == 'BlkDef'), "Argument 'maxFBlkTyp' is not of class BlkDef"
    assert(isinstance(RoCoFBlkTypList, Iterable)), "Argument 'RoCoFBlkTypList' is not an Iterable"
    for i, currRoCoFBlkTyp in enumerate(RoCoFBlkTypList):
        assert(isinstance(currRoCoFBlkTyp, pf.DataObject)), f"Argument 'RoCoFBlkTypList[{i}] is not of type powerfactory.DataObject"
    assert(isinstance(RoCoFBlkTypList, Iterable)), "Argument 'RoCoFBlkTypList' is not an Iterable"
    for i, currMaxRoCoFBlkTyp in enumerate(maxRoCoFBlkTypList):
        assert(isinstance(currMaxRoCoFBlkTyp, pf.DataObject)), f"Argument 'maxRoCoFBlkTypList[{i}] is not of type powerfactory.DataObject"
    assert(type(Gen) == pf.DataObject), "Argument 'Gen' is not of type powerfactory.DataObject"
    assert(Gen.GetClassName() == "ElmSym"), "Argument 'ElmSym' is not of class 'ElmSym'"
    assert(type(grid) == pf.DataObject), "Argument 'grid' is not of type powerfactory.DataObject"
    assert(grid.GetClassName() in ["ElmNet", "IntFolder"]), "Argument 'grid' is not of class ElmNet or IntFolder"

    exist_bool, Com = CheckIfDSLElmExists(name, grid, False)

    if exist_bool:
        print(f"Given composite model element {name} already exists, not creating new one")
        logging.info(f"Given composite model element {name} already exists, not creating new one")
        return(Com)
    RoCoFCompElm = grid.CreateObject("ElmComp", name)
    RoCoFCompElm.SetAttribute("typ_id", CompBlkTyp)

    minFBlkElm = RoCoFCompElm.CreateObject("ElmDsl", "minF")
    minFBlkElm.SetAttribute("typ_id", minFBlkTyp)

    maxFBlkElm = RoCoFCompElm.CreateObject("ElmDsl", "maxF")
    maxFBlkElm.SetAttribute("typ_id", maxFBlkTyp)

    RoCoFBlkElmList = []
    for i, currRoCoFBlkTyp in enumerate(RoCoFBlkTypList):
        RoCoFBlkElm = RoCoFCompElm.CreateObject("ElmDsl", f"RoCoF_{i}")
        RoCoFBlkElm.SetAttribute("typ_id", currRoCoFBlkTyp)
        RoCoFBlkElmList.append(RoCoFBlkElm)

    MaxRoCoFBlkElmList = []
    for i, currMaxRoCoFBlkTyp in enumerate(maxRoCoFBlkTypList):
        MaxRoCoFBlkElm = RoCoFCompElm.CreateObject("ElmDsl", f"MaxRoCoF_{i}")
        MaxRoCoFBlkElm.SetAttribute("typ_id", currMaxRoCoFBlkTyp)
        MaxRoCoFBlkElmList.append(MaxRoCoFBlkElm)

    pelm_list = [Gen, minFBlkElm, maxFBlkElm]+RoCoFBlkElmList+MaxRoCoFBlkElmList

    RoCoFCompElm.SetAttribute("pelm", pelm_list)

    return(RoCoFCompElm)

def SetCurrVenvInScript(script_path, iprint:bool) -> bool:
    venv_path = sys.prefix
    if iprint:
        if sys.prefix == sys.base_prefix:
            print("You're currently working in system python")
        else:
            print("Passing venv to script")
    package_path = os.path.join(venv_path,"Lib\\site-packages")
    venv_line = "venv_path = '" + str(package_path).replace("\\","\\\\") +"'\n"
    with open(script_path, "r", encoding='utf-8') as f:
        lines = f.readlines()

    lines[3] = venv_line
    with open(script_path, "w", encoding='utf-8') as f:
        f.writelines(lines)

def DefineInputFSA(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, M_settings: list) -> bool:
    ParamTypeInputList = ["double"]*len(M_settings)
    ParamNameInputList = []
    for i, M_set in enumerate(M_settings):
        ParamNameInputList.append(f'M_setting_{i}')
    ParamValueInputList = list(map(lambda x: str(x), M_settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def DefineInputFSA2(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, RoCoF_settings: list) -> bool:
    ParamTypeInputList = ["double"]*len(RoCoF_settings)
    ParamNameInputList = []
    for i, RoCoF_set in enumerate(RoCoF_settings):
        ParamNameInputList.append(f'RoCoF_setting_{i}')
    ParamValueInputList = list(map(lambda x: str(x), RoCoF_settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def setupStudyCasesFSA(sGenOut: list[pf.DataObject], MgridFolder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, M_settings: tuple[float], iprint: bool) -> tuple[list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenOut.

    The function takes the following arguments:\n
    :param sGenOut: a list of generators for which to create study cases.\n
    :param MgridFolder: The folder with the blocks that monitor output parameters.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: List of settings for dynamic simulation.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(sGenOut) == list), "The Argument 'sGenOut' is not of type list"
    for i in range(len(sGenOut)):
        assert(sGenOut[i].GetClassName() == "ElmSym"), "The Argument 'sGenOut["+str(i)+"] is not of class 'ElmSym'"
    assert(type(MgridFolder) == pf.DataObject), "The Argument 'MgridFolder' is not of type powerfactory.DataObject."
    assert(type(studyCaseFolder) == pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) == str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) == pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(M_settings) == tuple), "Given Argument 'M_settings' is not a list."
    for i,M_set in enumerate(M_settings):
        assert(type(M_set) in [int, float]), "Given Argument 'M_settings["+str(i)+"] in not of class int or float"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: list[pf.DataObject] = []
    createdComPython: list[pf.DataObject] = []
    
    # Create new StudyCase for each generator in sGenCCT
    for i, generator in enumerate(sGenOut):
        studyCaseName = f'Generator {generator.GetAttribute("loc_name")} outage.'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
                logging.info(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects

        DefineInputFSA(comPythonObject, MgridFolder, generator, M_settings)
        createdComPython.append(comPythonObject)
    
    return createdStudyCases, createdComPython

def setupStudyCasesFSA2(sGenOut: list[pf.DataObject], RoCoFgridFolder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, RoCoF_settings: tuple[float], iprint: bool) -> tuple[list[pf.DataObject], list[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenOut.

    The function takes the following arguments:\n
    :param sGenOut: a list of generators for which to create study cases.\n
    :param RoCoFgridFolder: The folder with the blocks that monitor output parameters.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param RoCoF_settings: List of settings for RoCoF calculation.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(sGenOut) == list), "The Argument 'sGenOut' is not of type list"
    for i in range(len(sGenOut)):
        assert(sGenOut[i].GetClassName() == "ElmSym"), "The Argument 'sGenOut["+str(i)+"] is not of class 'ElmSym'"
    assert(type(RoCoFgridFolder) == pf.DataObject), "The Argument 'RoCoFgridFolder' is not of type powerfactory.DataObject."
    assert(type(studyCaseFolder) == pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) == str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) == pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(RoCoF_settings) == tuple), "Given Argument 'RoCoF_settings' is not a list."
    for i,RoCoF_set in enumerate(RoCoF_settings):
        assert(isinstance(RoCoF_set, (int, float))), f"Given Argument 'RoCoF_set[{i}] in not of class int or float"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: list[pf.DataObject] = []
    createdComPython: list[pf.DataObject] = []
    
    # Create new StudyCase for each generator in sGenCCT
    for i, generator in enumerate(sGenOut):
        studyCaseName = f'Generator {generator.GetAttribute("loc_name")} outage.'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
                logging.info(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects

        DefineInputFSA2(comPythonObject, RoCoFgridFolder, generator, RoCoF_settings)
        createdComPython.append(comPythonObject)
    
    return createdStudyCases, createdComPython

def FSASingleGenerator(app: pf.Application, M_settings_vals: list[float], AllMComp: list[pf.DataObject], oGenOut: pf.DataObject,  iprint: bool):
    '''
    This function is meant to be called from external processing script.

    :param app: The powerfactory application in which the desired project should already be activated.\n
    :param M_settings_vals: The desired thresholds for M values:\n
    :param AllMComp: The monitoring blocks for output values.\n
    :param oGenOut: The generator whose outage is calculated.\n
    :param iprint: A boolean that determines if the results should be printed\n
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(M_settings_vals) == list), "Given Argument 'settings' is not a list."
    for i, M_val in enumerate(M_settings_vals):
        assert(type(M_val) in [int, float]), "Given argument 'M_settings_vals["+str(i)+"]' is of type int or float. "
    assert(type(AllMComp) == list), "Given Argument 'AllMComp' is not of type list."
    assert(type(oGenOut) == pf.DataObject), "Given argument 'oGenOut' is not of type powerfactory.DataObject."
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")

    currGenName = getForOrLocName(oGenOut)

    oGenOutEvt, initUserEvts = setFSAEvents(oComInc)

    oGenOutEvt.p_target = oGenOut
    oComInc.Execute()
    oComSim.Execute()

    FSA_data = []
    for i in AllMComp:
            currMonGenData = []
            minMLst = []
            # Get elements
            for Elm in i.GetAttribute("pelm"):
                if Elm.GetClassName() == "ElmSym":
                    currGenMon = Elm
                    currElmName = getForOrLocName(currGenMon)
                if Elm.loc_name == "maxRoCoF":
                    currElmMaxRoCoF = Elm.GetAttribute("c:max_RoCoF")
                if Elm.loc_name == "minF":
                    currElmMinFreq = Elm.GetAttribute("c:min_freq")
                if Elm.loc_name == "maxF":
                    currElmMaxFreq = Elm.GetAttribute("c:max_freq")
                if "minM_" in Elm.loc_name:
                    minMLst.append(Elm.GetAttribute("c:min_M"))
            # You don't want to monitor the generator that is tripped as it is not
            # synchronised anyways.
            if oGenOut in i.GetAttribute("pelm"):
                continue
            currMonGenData = (currElmName, currElmMinFreq, currElmMaxFreq, currElmMaxRoCoF, minMLst)
            currGenData = (currGenName, currMonGenData)
            FSA_data.append(currGenData)

    return (FSA_data)

def FSASingleGenerator2(app: pf.Application, RoCoF_settings_vals: list[float], AllRoCoFComp: list[pf.DataObject], oGenOut: pf.DataObject,  iprint: bool):
    '''
    This function is meant to be called from external processing script.

    :param app: The powerfactory application in which the desired project should already be activated.\n
    :param RoCoF_settings_vals: The desired windows for RoCoF calculations.\n
    :param AllRoCoFComp: The monitoring blocks for output values.\n
    :param oGenOut: The generator whose outage is calculated.\n
    :param iprint: A boolean that determines if the results should be printed\n
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(isinstance(RoCoF_settings_vals, Iterable)), "Given Argument 'RoCoF_settings_vals' is not an iterable."
    for i, RoCoF_val in enumerate(RoCoF_settings_vals):
        assert(type(RoCoF_val) in [int, float]), f"Given argument 'RoCoF_settings_vals[{i}]' is not a number. "
    assert(isinstance(AllRoCoFComp, Iterable)), "Given Argument 'AllRoCoFComp' is not an iterable."
    assert(type(oGenOut) == pf.DataObject), "Given argument 'oGenOut' is not of type powerfactory.DataObject."
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")

    currGenName = getForOrLocName(oGenOut)

    oGenOutEvt, initUserEvts = setFSAEvents(oComInc)

    oGenOutEvt.p_target = oGenOut
    oComInc.Execute()
    oComSim.Execute()

    FSA_data = []
    for i in AllRoCoFComp:
            currMonGenData = []
            maxRoCoFList = []
            # Get elements
            for Elm in i.GetAttribute("pelm"):
                if Elm.GetClassName() == "ElmSym":
                    currGenMon = Elm
                    currElmName = getForOrLocName(currGenMon)
                if Elm.loc_name == "minF":
                    currElmMinFreq = Elm.GetAttribute("c:min_freq")
                if Elm.loc_name == "maxF":
                    currElmMaxFreq = Elm.GetAttribute("c:max_freq")
                if "MaxRoCoF_" in Elm.loc_name:
                    maxRoCoFList.append(Elm.GetAttribute("c:max_RoCoF"))

            # You don't want to monitor the generator that is tripped as it is not
            # synchronised anyways.
            if oGenOut in i.GetAttribute("pelm"):
                continue
            currMonGenData = (currElmName, currElmMinFreq, currElmMaxFreq, maxRoCoFList)
            currGenData = (currGenName, currMonGenData)
            FSA_data.append(currGenData)

    return (FSA_data)

def ReadResFilesFSA(sGenOut: list[pf.DataObject], tempResultsDir: str, ) -> list[list]:
    FSA_data_lists: list[list] = []
    for id, generator in enumerate(sGenOut):
        generatorName = getForOrLocName(generator)
        if ":" in generatorName:
            index = generatorName.find(":")
            generatorName = generatorName[index+1:]
        file_indexing = 0
        tempFilePath = f"{tempResultsDir}\\FSAdata_{generatorName}_{file_indexing}.pkl"
        while os.path.exists(tempFilePath):
            try:
                FSAResults = HandleFiles.loadResultsFromTemporaryFile(tempFilePath)
                if FSAResults is not None:
                    FSA_data_lists.append(FSAResults)
                else:
                    # This case might occur if the file exists but is empty or corrupted in a way that load returns None
                    print(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
                    logging.warning(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
            except FileNotFoundError:
                print(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
                logging.error(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
            except Exception as e: # Catch other potential errors during loading (e.g., pickle errors)
                print(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
                logging.error(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
            file_indexing = file_indexing + 1
            tempFilePath = f"{tempResultsDir}\\FSAdata_{generatorName}_{file_indexing}.pkl"
    
    return(FSA_data_lists)

def ReadResFilesFSA(sGenOut: list[pf.DataObject], tempResultsDir: str, ) -> list[list]:
    FSA_data_lists: list[list] = []
    for id, generator in enumerate(sGenOut):
        generatorName = getForOrLocName(generator)
        if ":" in generatorName:
            index = generatorName.find(":")
            generatorName = generatorName[index+1:]
        file_indexing = 0
        tempFilePath = f"{tempResultsDir}\\FSAdata_{generatorName}_{file_indexing}.pkl"
        while os.path.exists(tempFilePath):
            try:
                FSAResults = HandleFiles.loadResultsFromTemporaryFile(tempFilePath)
                if FSAResults is not None:
                    FSA_data_lists.append(FSAResults)
                else:
                    # This case might occur if the file exists but is empty or corrupted in a way that load returns None
                    print(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
                    logging.warning(f"Loaded results are None for generator {generatorName} from {tempFilePath}.")
            except FileNotFoundError:
                print(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
                logging.error(f"Temporary results file not found for generator {generatorName}: {tempFilePath}")
            except Exception as e: # Catch other potential errors during loading (e.g., pickle errors)
                print(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
                logging.error(f"Failed to load results for generator {generatorName} from {tempFilePath}. Error: {e}")
            file_indexing = file_indexing + 1
            tempFilePath = f"{tempResultsDir}\\FSAdata_{generatorName}_{file_indexing}.pkl"
    
    return(FSA_data_lists)

def RedefineToOriginalElementsFSATreshold(app: pf.Application, whole_FSA_info_lists: list[list]) -> list[list]:
    for index, FSA_entry in enumerate(whole_FSA_info_lists):
        original_generator_outage = FSA_entry[0]
        original_gneerator_monitoring = FSA_entry[1][0]

        try:
            # Try to get the gen outage object
            gen_out_objects = app.GetCalcRelevantObjects(f"*{original_generator_outage}")
            if gen_out_objects: # Check if the list is not empty
                whole_FSA_info_lists[index][0] = gen_out_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_generator_outage}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_generator_outage}: {e}. Keeping original reference.")

        try:
            # Try to get the gen monitor object
            gen_mon_objects = app.GetCalcRelevantObjects(f"*{original_gneerator_monitoring}")
            if gen_mon_objects: # Check if the list is not empty
                whole_FSA_info_lists[index][1][0] = gen_mon_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_gneerator_monitoring}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_gneerator_monitoring}: {e}. Keeping original reference.")

    return whole_FSA_info_lists
def CleanupTemp(tempResultsDir: str) -> bool:
    filepaths = [os.path.join(tempResultsDir, filename) for filename in os.listdir(tempResultsDir)]
    for filepath in filepaths:
        if "FSAdata_" in filepath:
            try:
                os.remove(filepath)
            except FileNotFoundError:
                logging.warning(f"Temporary file not found during cleanup, skipping removal: {filepath}")
            except OSError as e:
                logging.error(f"Error removing temporary file {filepath}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error removing temporary file {filepath}: {e}")
    return True

# main function

def FSA(app: pf.Application, settings: tuple[float, float, float, bool, tuple[float], tuple[float], tuple[float]], grid: pf.DataObject, sGenOut: list[pf.DataObject], sGenMon: list[pf.DataObject], sLodLFDD: list[pf.DataObject], iprint: bool) -> list[tuple[pf.DataObject, tuple[str, float, float, float, list[float]]]]:
    '''
    This function runs the frequency stability assessment for generator outages given with 'sGenOut'. The frequency indicies are monitored on generators at 'sGenMon'.
    The Arguments to the funciton are:\n

    app - the powerfactory application in which the desired project should already be activated.\n
    settings - the desired settings tuple which should cosist od (in that order): \n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] Should LFDD be implementer? \n
        - [4] The frequency treshold tuple for the under frequency load shedding (LFDD) scheme stages (in p.u.)\n
        - [5] The load reduction tuple for the under frequency load shedding (LFDD) scheme stages (in %). Note, that
        the values should be negative\n
        - [6] The frequency border tuple for the M calcualting scheme (in p.u.)\n
    grid - the grid in which the LFDD dynamic model and the Measurment dynamic models should be stored\n
    sGenOut - The list of generators, whose outages should be considered\n
    sGenMon - The list of generators, whose values should be considered\n
    sLodLFDD - The list of loads, which should be considered during the LFDD scheme\n
    iprint - If the intermediate messages should be printed\n

    The function returns a list of lists. The number of inner lists is equal to the number of outages to be evaluated. Each inner list consists of:\n
        - [0] the name of the generator that fell out
        - [1:n+1] n lists (where n is the number of monitored generators excluding the generator that fell out), which contains:
            *[0] the name of the generator which is monitored]
            *[1] the name maximum rocof of the monitored generator
            *[2] the minimum frequency of the monitored generator
            *[3] the maximum frequency of the monitored generator
            *[4] a list of M values of the monitored generator. The lengths of the list depends on the Argument given with "settings [3]" (the threshold list of M values)
    '''

    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application"
    assert(type(settings) == tuple), "Argument 'settings' is not of type tuple"
    assert(len(settings) == 7),"Argument 'settings' does not have 6 entrys. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] Should LFDD be considered? \n\
                                - [4] The frequency treshold list for the under frequency load shedding (LFDD) scheme stages (in p.u.)\n\
                                - [5] The laod reduction list for the under frequency load shedding (LFDD) scheme stages (in %). Note, that\
                                the values should be negative\n\
                                - [6] The frequency border list for the M calcualting scheme (in p.u.)"
    assert(type(settings[0]) in [int, float]), "Argument 'settings[0]' should be of type int of float"
    assert(type(settings[1]) in [int, float]), "Argument 'settings[1]' should be of type int of float"
    assert(type(settings[2]) in [int, float]), "Argument 'settings[2]' should be of type int of float"
    assert(type(settings[3]) == bool), "Argument 'settings[3]' should be of type bool"
    assert(type(settings[4]) == tuple), "Argument 'settings[4]' should be of type list"
    for i in range(len(settings[4])):
        assert(type(settings[4][i]) in [int, float]), "Argument 'settings[4]["+str(i)+"] should be of type int or float"
    for i in range(len(settings[5])):
        assert(type(settings[5][i]) in [int,float]), "Argument 'settings[5]["+str(i)+"] should be of type int or float"
    for i in range(len(settings[6])):
        assert(type(settings[6][i]) in [int,float]), "Argument 'settings[6]["+str(i)+"] should be of type int or float"
    assert(type(grid) == pf.DataObject), "Argument 'grid' should be of type powerfactory.DataObject"
    assert(grid.GetClassName() == "ElmNet"), "Argument 'grid' should be of class 'ElmNet'"
    assert(type(sGenOut) == list), "Argument 'sGenOut' should be of type list"
    for i in range(len(sGenOut)):
        assert(type(sGenOut[i]) == pf.DataObject), "Argument 'sGenOut["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sGenOut[i].GetClassName() == "ElmSym"), "Argument 'sGenOut["+str(i)+"]' should be of class 'ElmSym'"
    assert(type(sGenMon) == list), "Argument 'sGenMon' should be of type list"
    for i in range(len(sGenMon)):
        assert(type(sGenMon[i]) == pf.DataObject), "Argument 'sGenMon["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sGenMon[i].GetClassName() == "ElmSym"), "Argument 'sGenMon["+str(i)+"]' should be of class 'ElmSym'"
    assert(type(sLodLFDD) == list), "Argument 'sLodLFDD' should be of type list"
    for i in range(len(sLodLFDD)):
        assert(type(sLodLFDD[i]) == pf.DataObject), "Argument 'sLodLFDD["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sLodLFDD[i].GetClassName() == "ElmLod"), "Argument 'sLodLFDD["+str(i)+"]' should be of class 'ElmLod'"
    assert(type(iprint) == bool), "Argument 'iprint' should be of type bool"

    # get simulation comands
    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    dynFolder = app.GetProjectFolder("blk")
    if settings[3]:
        LFDDdynTypFolder = dynFolder.CreateObject("IntFolder", "LFDDdynTyp")
    MdynTypFolder = dynFolder.CreateObject("IntFolder", "MdynTyp")

    if settings[3]:
        LFDDgridFolder = grid.CreateObject("IntFolder", "LFDDDynamicModels")
    MgridFolder = grid.CreateObject("IntFolder", "MDynamicModels")

    initUserParams = setUserParamas(oComInc, oComSim,settings[0], settings[1], settings[2])
    oGenOutEvt, initUserEvts = setFSAEvents(oComInc)
    
    if settings[3]:
        LFDDBlkTyp, LFDDFolders = LFDD.CreateLFDDScheme(LFDDgridFolder, LFDDdynTypFolder, sLodLFDD, settings[4], settings[5])
    MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst = CreateMCompBlkTyp("MComBlkTyp", MdynTypFolder, settings[6])
    
    allMComp = []
    for oGen in sGenMon:
        MCompElm = CreateMCompElm("MCompBlkElm_"+str(oGen.loc_name), MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst, oGen, MgridFolder)
        allMComp.append(MCompElm)
    # FSA data structure [[GenThatGotCut,[MonitoredGenerator, maxRocof, minFreq, maxFreq, [Mvalues]],[-||-]],[-||-],]
    FSA_data = []
    for oGen in tqdm.tqdm(sGenOut):
        currGenData = []
        currGenName = getForOrLocName(oGen)
        oGenOutEvt.p_target = oGen
        oComInc.Execute()
        oComSim.Execute()
        for i in allMComp:
            currMonGenData = []
            minMLst = []
            # Get elements
            for Elm in i.GetAttribute("pelm"):
                if Elm.GetClassName() == "ElmSym":
                    currGenMon = Elm
                    currElmName = getForOrLocName(currGenMon)
                if Elm.loc_name == "maxRoCoF":
                    currElmMaxRoCoF = Elm.GetAttribute("c:max_RoCoF")
                if Elm.loc_name == "minF":
                    currElmMinFreq = Elm.GetAttribute("c:min_freq")
                if Elm.loc_name == "maxF":
                    currElmMaxFreq = Elm.GetAttribute("c:max_freq")
                if "minM_" in Elm.loc_name:
                    minMLst.append(Elm.GetAttribute("c:min_M"))
            # You don't want to monitor the generator that is tripped as it is not
            # synchronised anyways.
            if oGen in i.GetAttribute("pelm"):
                continue
            currMonGenData = (currElmName, currElmMinFreq, currElmMaxFreq, currElmMaxRoCoF , minMLst)
            currGenData = (currGenName, currMonGenData)
            FSA_data.append(currGenData)

    oComReset.Execute()

    if settings[3]:
        LFDDgridFolder.Delete()
        LFDDdynTypFolder.Delete()

    MdynTypFolder.Delete()
    MgridFolder.Delete()

    setInitialParams(oComInc, oComSim, initUserParams)
    setInitialEvents(oGenOutEvt, initUserEvts)

    return(FSA_data)

def FSAParallel(app: pf.Application, settings: tuple[float, float, float, bool, tuple[float], tuple[float], tuple[float]], grid: pf.DataObject, sGenOut: list[pf.DataObject], sGenMon: list[pf.DataObject], sLodLFDD: list[pf.DataObject], iprint: bool) -> list[tuple[pf.DataObject, tuple[str, float, float, float, list[float]]]]:
    '''
    Run frequency stability analysis for a group of generators in parallel.

    This function sets up and executes parallel FSA simulations by creating
    seperate study cases and ComPython scripts for each generator contingency.
    It then uses a ComTask object to manage the parallel execution within PowerFactory.

    Note: Parallel exection might not improve performance for already fast
    sequential runs (e.g., < 150s). Consider using 'FSA' in such cases.

    :param app: The PowerFactory application object with the desired project activated.
    :param settings: List of settings for dynamic simulation.
    :param grid: The grid in which to store OutOfStep blocks.
    :param sGenOut: List of generators whose outage to consider.
    :param sGenMon: List of generators whose speed to monitor.
    :param sLodLFDD: List of loads to be considered in under-frequency load shedding scheme.
    :param iprint: Flag to control printing of progress messages during setup.
    '''

    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application"
    assert(type(settings) == tuple), "Argument 'settings' is not of type tuple"
    assert(len(settings) == 7),"Argument 'settings' does not have 6 entrys. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] Should LFDD be implemented? \n\
                                - [4] The frequency treshold list for the under frequency load shedding (LFDD) scheme stages (in p.u.)\n\
                                - [5] The laod reduction list for the under frequency load shedding (LFDD) scheme stages (in %). Note, that\
                                the values should be negative\n\
                                - [6] The frequency border list for the M calcualting scheme (in p.u.)"
    assert(type(settings[0]) in [int, float]), "Argument 'settings[0]' should be of type int of float"
    assert(type(settings[1]) in [int, float]), "Argument 'settings[1]' should be of type int of float"
    assert(type(settings[2]) in [int, float]), "Argument 'settings[2]' should be of type int of float"
    assert(type(settings[3]) == bool), "Argument 'settings[3]' should be of type bool"
    assert(type(settings[4]) == tuple), "Argument 'settings[4]' should be of type list"
    for i in range(len(settings[4])):
        assert(type(settings[4][i]) in [int, float]), "Argument 'settings[4]["+str(i)+"] should be of type int or float"
    for i in range(len(settings[5])):
        assert(type(settings[5][i]) in [int,float]), "Argument 'settings[5]["+str(i)+"] should be of type int or float"
    for i in range(len(settings[6])):
        assert(type(settings[6][i]) in [int,float]), "Argument 'settings[6]["+str(i)+"] should be of type int or float"
    assert(type(grid) == pf.DataObject), "Argument 'grid' should be of type powerfactory.DataObject"
    assert(grid.GetClassName() == "ElmNet"), "Argument 'grid' should be of class 'ElmNet'"
    assert(type(sGenOut) == list), "Argument 'sGenOut' should be of type list"
    for i in range(len(sGenOut)):
        assert(type(sGenOut[i]) == pf.DataObject), "Argument 'sGenOut["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sGenOut[i].GetClassName() == "ElmSym"), "Argument 'sGenOut["+str(i)+"]' should be of class 'ElmSym'"
    assert(type(sGenMon) == list), "Argument 'sGenMon' should be of type list"
    for i in range(len(sGenMon)):
        assert(type(sGenMon[i]) == pf.DataObject), "Argument 'sGenMon["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sGenMon[i].GetClassName() == "ElmSym"), "Argument 'sGenMon["+str(i)+"]' should be of class 'ElmSym'"
    assert(type(sLodLFDD) == list), "Argument 'sLodLFDD' should be of type list"
    for i in range(len(sLodLFDD)):
        assert(type(sLodLFDD[i]) == pf.DataObject), "Argument 'sLodLFDD["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sLodLFDD[i].GetClassName() == "ElmLod"), "Argument 'sLodLFDD["+str(i)+"]' should be of class 'ElmLod'"
    assert(type(iprint) == bool), "Argument 'iprint' should be of type bool"

    activeProject: pf.DataObject = app.GetActiveProject()
    
    # get active study case name
    ActStudCaseName = os.getenv("stud_case")

    # get simulation comands
    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    dynFolder = app.GetProjectFolder("blk")
    if settings[3]:
        LFDDdynTypFolder = dynFolder.CreateObject("IntFolder", "LFDDdynTyp")
    MdynTypFolder = dynFolder.CreateObject("IntFolder", "MdynTyp")

    if settings[3]:
        LFDDgridFolder = grid.CreateObject("IntFolder", "LFDDDynamicModels")
    MgridFolder = grid.CreateObject("IntFolder", "MDynamicModels")

    initUserParams = setUserParamas(oComInc, oComSim,settings[0], settings[1], settings[2])
    oGenOutEvt, initUserEvts = setFSAEvents(oComInc)
    
    if settings[3]:
        LFDDBlkTyp, LFDDFolders = LFDD.CreateLFDDScheme(LFDDgridFolder, LFDDdynTypFolder, sLodLFDD, settings[3], settings[4])
    MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst = CreateMCompBlkTyp("MComBlkTyp", MdynTypFolder, settings[6])
    
    allMComp = []
    for oGen in sGenMon:
        MCompElm = CreateMCompElm("MCompBlkElm_"+str(oGen.loc_name), MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst, oGen, MgridFolder)
        allMComp.append(MCompElm)

    # Obtain Study Cases folder from the project
    studyCaseFolder: pf.DataObject = activeProject.GetContents("Study Cases.IntPrjfolder", 1)[0]
    if studyCaseFolder is None:
        print("Failed to retrieve the Study Case folder.")
        logging.error("Failed to retrieve the Study Case folder.")
        raise ValueError("Study Case folder not found.")
    
    # Obtain the base StudyCase that we will create copies of
    baseStudyCase: pf.DataObject = studyCaseFolder.GetContents(ActStudCaseName, 1)[0]
    if baseStudyCase is None:
        print("Failed to retrieve the base Study Case.")
        logging.error("Failed to retrieve the base Study Case.")
        raise ValueError("Base Study Case not found.")

    # Setup parallelisation script path
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    basePath = os.path.dirname(scriptDir) # Go one level up from the script's directory
    targetScriptRelativePath = os.path.join('parallelisation', "FSA.py")
    targetScriptPath = os.path.join(basePath, targetScriptRelativePath)
    
    # set parallelisation script package path
    SetCurrVenvInScript(targetScriptPath, iprint)

    # Setup temporary results directory (needs te be set the same path as in parallelisation script SAUntilTreshold.py)
    tempResultsDir = os.path.join(basePath, "parallelisation\\temp_results")

    # Create StudyCases for parallelisation
    createdStudyCases, createdComPython = setupStudyCasesFSA(sGenOut, MgridFolder, studyCaseFolder, targetScriptPath, baseStudyCase, settings[6], iprint)
    # Create ComTask in Study Cases folder (Task Automation)
    comTask = studyCaseFolder.CreateObject("ComTasks", "Avtomatizacija")

    # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
    for id, studyCase in enumerate(createdStudyCases):
        comTask.AppendStudyCase(studyCase) # type: ignore
        comTask.AppendCommand(createdComPython[id], 0) # type: ignore

    # force Task automation to use parallel computing
    comTask.SetAttribute("minTasks4Par", 1)
    
    # Execute the ComTask command
    if iprint:
        print("Executing ComTask command. Transferring data to parallel processes and starting execution...")
        logging.info("Executing ComTask command. Transferring data to parallel processes and starting execution...")
    iComTaskExecute = comTask.Execute() # type: ignore
    if iprint:
        print("ComTask command finished.")
        logging.info("ComTask command finished.")

    # Get output from the OutputWindow (to check if everything went well)
    outputContent = PFSupport.Utils.getOutputWindowContent(app)
    if isinstance(outputContent, list):
        for line in outputContent:
            logging.info(f"PF OutputWindow: {line}")
    else:
        logging.info(f"PF OutputWindow: {outputContent}")

    # Read all the results from the temporary files created by the ComPython scripts
    FSA_data_lists = ReadResFilesFSA(sGenOut, tempResultsDir)
    
    final_output = []
    for i in FSA_data_lists:
        final_output = final_output + i

    # Clean up temporary files
    CleanupTemp(tempResultsDir)

    # Reset to initial settings
    oComReset.Execute()

    if settings[3]:
        LFDDgridFolder.Delete()
        LFDDdynTypFolder.Delete()

    MdynTypFolder.Delete()
    MgridFolder.Delete()

    setInitialParams(oComInc, oComSim, initUserParams)
    setInitialEvents(oGenOutEvt, initUserEvts)
    
    # Clean up created study cases
    for studyCase in createdStudyCases:
        studyCase.Delete()

    return final_output

def FSAParallel2(app: pf.Application, settings: tuple[float, float, float, bool, tuple[float], tuple[float]], grid: pf.DataObject, sGenOut: list[pf.DataObject], sGenMon: list[pf.DataObject], sLodLFDD: list[pf.DataObject], iprint: bool) -> list[tuple[pf.DataObject, tuple[str, float, float, float, list[float]]]]:
    '''
    Run frequency stability analysis for a group of generators in parallel.

    This function sets up and executes parallel FSA simulations by creating
    seperate study cases and ComPython scripts for each generator contingency.
    It then uses a ComTask object to manage the parallel execution within PowerFactory.

    Note: Parallel exection might not improve performance for already fast
    sequential runs (e.g., < 150s). Consider using 'FSA' in such cases.

    :param app: The PowerFactory application object with the desired project activated.
    :param settings: List of settings for dynamic simulation.
    :param grid: The grid in which to store OutOfStep blocks.
    :param sGenOut: List of generators whose outage to consider.
    :param sGenMon: List of generators whose speed to monitor.
    :param sLodLFDD: List of loads to be considered in under-frequency load shedding scheme.
    :param iprint: Flag to control printing of progress messages during setup.
    '''

    assert(type(app) == pf.Application), "Argument 'app' is not of type powerfactory.Application"
    assert(type(settings) == tuple), "Argument 'settings' is not of type tuple"
    assert(len(settings) == 7),"Argument 'settings' does not have 6 entrys. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] Should LFDD be implemented? \n\
                                - [4] The frequency treshold list for the under frequency load shedding (LFDD) scheme stages (in p.u.)\n\
                                - [5] The laod reduction list for the under frequency load shedding (LFDD) scheme stages (in %). Note, that the values should be negative\n\
                                - [6] the moving average window sizes for RoCoF calculation."
    assert(type(settings[0]) in [int, float]), "Argument 'settings[0]' should be of type int of float"
    assert(type(settings[1]) in [int, float]), "Argument 'settings[1]' should be of type int of float"
    assert(type(settings[2]) in [int, float]), "Argument 'settings[2]' should be of type int of float"
    assert(type(settings[3]) == bool), "Argument 'settings[3]' should be of type bool"
    assert(type(settings[4]) == tuple), "Argument 'settings[4]' should be of type tuple"
    assert(isinstance(settings[5], tuple)), "Argument 'settings[5]' should be of type tuple"
    assert(isinstance(settings[6], tuple)), "Argument 'settings[6]' should be of type tuple"
    for i in range(len(settings[4])):
        assert(type(settings[4][i]) in [int, float]), "Argument 'settings[4]["+str(i)+"] should be of type int or float"
    for i in range(len(settings[5])):
        assert(type(settings[5][i]) in [int,float]), "Argument 'settings[5]["+str(i)+"] should be of type int or float"
    for i, setting in enumerate(settings[6]):
        assert(isinstance(setting, (int, float))), f"Argument 'settings[6][{i}] is not a number"
    assert(type(grid) == pf.DataObject), "Argument 'grid' should be of type powerfactory.DataObject"
    assert(grid.GetClassName() == "ElmNet"), "Argument 'grid' should be of class 'ElmNet'"
    assert(type(sGenOut) == list), "Argument 'sGenOut' should be of type list"
    for i in range(len(sGenOut)):
        assert(type(sGenOut[i]) == pf.DataObject), "Argument 'sGenOut["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sGenOut[i].GetClassName() == "ElmSym"), "Argument 'sGenOut["+str(i)+"]' should be of class 'ElmSym'"
    assert(type(sGenMon) == list), "Argument 'sGenMon' should be of type list"
    for i in range(len(sGenMon)):
        assert(type(sGenMon[i]) == pf.DataObject), "Argument 'sGenMon["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sGenMon[i].GetClassName() == "ElmSym"), "Argument 'sGenMon["+str(i)+"]' should be of class 'ElmSym'"
    assert(type(sLodLFDD) == list), "Argument 'sLodLFDD' should be of type list"
    for i in range(len(sLodLFDD)):
        assert(type(sLodLFDD[i]) == pf.DataObject), "Argument 'sLodLFDD["+str(i)+"]' should be of type powerfactory.DataObject"
        assert(sLodLFDD[i].GetClassName() == "ElmLod"), "Argument 'sLodLFDD["+str(i)+"]' should be of class 'ElmLod'"
    assert(type(iprint) == bool), "Argument 'iprint' should be of type bool"

    activeProject: pf.DataObject = app.GetActiveProject()
    
    # get active study case name
    ActStudCaseName = os.getenv("stud_case")

    # get simulation comands
    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    dynFolder = app.GetProjectFolder("blk")
    if settings[3]:
        LFDDdynTypFolder = dynFolder.CreateObject("IntFolder", "LFDDdynTyp")
    # MdynTypFolder = dynFolder.CreateObject("IntFolder", "MdynTyp")
    RoCoFTypFolder = dynFolder.CreateObject("IntFolder", "RoCoFDynTyp")

    if settings[3]:
        LFDDgridFolder = grid.CreateObject("IntFolder", "LFDDDynamicModels")
    # MgridFolder = grid.CreateObject("IntFolder", "MDynamicModels")
    RoCoFGridFolder = grid.CreateObject("IntFolder", "RoCoFDynamicModels")

    initUserParams = setUserParamas(oComInc, oComSim,settings[0], settings[1], settings[2])
    oGenOutEvt, initUserEvts = setFSAEvents(oComInc)
    
    if settings[3]:
        LFDDBlkTyp, LFDDFolders = LFDD.CreateLFDDScheme(LFDDgridFolder, LFDDdynTypFolder, sLodLFDD, settings[3], settings[4])
    # MComBlkTyp, RoCoFBlkTyp, minFBlkTyp, maxFBlkTyp, maxRoCoFBlkTyp, MBlkTypLst, MinMBlkTypLst = CreateMCompBlkTyp("MComBlkTyp", MdynTypFolder, settings[6])
    RoCoFCompBlkTyp, minFBlkTyp, maxFBlkTyp, RoCoFBlkTypList, maxRoCoFBlkTypList = CreateRoCoFCompBlkTyp2("RoCoFComBlkTyp", RoCoFTypFolder, settings[6], settings[2])
    
    allRoCoFComp = []
    for i, oGen in enumerate(sGenMon):
        RoCoFCompElm = CreateRoCoFCompElm(f"RoCoFCompBlkElm_{oGen.loc_name}", RoCoFCompBlkTyp, minFBlkTyp, maxFBlkTyp, RoCoFBlkTypList, maxRoCoFBlkTypList, oGen, RoCoFGridFolder)
        allRoCoFComp.append(RoCoFCompElm)

    # Obtain Study Cases folder from the project
    studyCaseFolder: pf.DataObject = activeProject.GetContents("Study Cases.IntPrjfolder", 1)[0]
    if studyCaseFolder is None:
        print("Failed to retrieve the Study Case folder.")
        logging.error("Failed to retrieve the Study Case folder.")
        raise ValueError("Study Case folder not found.")
    
    # Obtain the base StudyCase that copies of will be created
    baseStudyCase: pf.DataObject = studyCaseFolder.GetContents(ActStudCaseName, 1)[0]
    if baseStudyCase is None:
        print("Failed to retrieve the base Study Case.")
        logging.error("Failed to retrieve the base Study Case.")
        raise ValueError("Base Study Case not found.")
    # Setup parallelisation script path
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    basePath = os.path.dirname(scriptDir) # Go one level up from the script's directory
    targetScriptRelativePath = os.path.join('parallelisation', "FSA2.py")
    targetScriptPath = os.path.join(basePath, targetScriptRelativePath)
    
    # set parallelisation script package path
    SetCurrVenvInScript(targetScriptPath, iprint)

    # Setup temporary results directory (needs te be set the same path as in parallelisation script SAUntilTreshold.py)
    tempResultsDir = os.path.join(basePath, "parallelisation\\temp_results")

    # Create StudyCases for parallelisation
    createdStudyCases, createdComPython = setupStudyCasesFSA2(sGenOut, RoCoFGridFolder, studyCaseFolder, targetScriptPath, baseStudyCase, settings[6], iprint)
    # Create ComTask in Study Cases folder (Task Automation)
    comTask = studyCaseFolder.CreateObject("ComTasks", "Avtomatizacija")

    # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
    for id, studyCase in enumerate(createdStudyCases):
        comTask.AppendStudyCase(studyCase) # type: ignore
        comTask.AppendCommand(createdComPython[id], 0) # type: ignore

    # force Task automation to use parallel computing
    comTask.SetAttribute("minTasks4Par", 1)
    
    # Execute the ComTask command
    if iprint:
        print("Executing ComTask command. Transferring data to parallel processes and starting execution...")
        logging.info("Executing ComTask command. Transferring data to parallel processes and starting execution...")
    iComTaskExecute = comTask.Execute() # type: ignore
    if iprint:
        print("ComTask command finished.")
        logging.info("ComTask command finished.")

    # Get output from the OutputWindow (to check if everything went well)
    outputContent = PFSupport.Utils.getOutputWindowContent(app)
    if isinstance(outputContent, list):
        for line in outputContent:
            logging.info(f"PF OutputWindow: {line}")
    else:
        logging.info(f"PF OutputWindow: {outputContent}")

    # Read all the results from the temporary files created by the ComPython scripts
    FSA_data_lists = ReadResFilesFSA(sGenOut, tempResultsDir)
    
    final_output = []
    for i in FSA_data_lists:
        final_output = final_output + i

    # Clean up temporary files
    CleanupTemp(tempResultsDir)

    # Reset to initial settings
    oComReset.Execute()

    if settings[3]:
        LFDDgridFolder.Delete()
        LFDDdynTypFolder.Delete()

    RoCoFTypFolder.Delete()
    RoCoFGridFolder.Delete()

    setInitialParams(oComInc, oComSim, initUserParams)
    setInitialEvents(oGenOutEvt, initUserEvts)
    
    # Clean up created study cases
    for studyCase in createdStudyCases:
        studyCase.Delete()

    return final_output

def CalculateInertia(app: pf.Application, HGrids: list[pf.DataObject]):
    """
    This function calculates of the total rotational kinetical energy (Wk), the total inertial constant (H) and the centre of inertia inertial
    constant (HCoI) for the desired grids.
    
    :param app: The PowerFactory application where the desired project for inertia calculation should be active.
    :type app: pf.Application
    :param InertiaGrid: A list of grids, in which the the inertia should be calculated in.
    :type InertiaGrid: list[pf.DataObject]
    """

    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    for i, CurrGrid in enumerate(HGrids):
        assert(type(CurrGrid) == pf.DataObject), "Given argument 'InertiaGrid["+str(i)+"]' is not of type PowerFactory.DataObject"
        assert(CurrGrid.GetClassName() == "ElmNet"), "Given argument 'InertiaGrid["+str(i)+"]' is not of class 'ElmNet'"

    Hmax = 0
    Htotal = 0
    Wkmax = 0
    WkTotal = 0
    Stotal = 0
    sAllGens = app.GetCalcRelevantObjects("*.ElmSym")
    for oGen in sAllGens:
        oGenGrid = oGen.GetAttribute("cpGrid")
        if oGenGrid in HGrids:
            oGenTyp = oGen.GetAttribute("typ_id")
            currH = oGenTyp.GetAttribute("h")
            currS = oGenTyp.GetAttribute("sgn")
            Hmax += currH
            currWk = currH*currS
            Wkmax += currWk
            if oGen.GetAttribute("outserv") == 0:
                Htotal += currH
                WkTotal += currWk
                Stotal += currS

    HCoI = WkTotal/Stotal

    return([WkTotal, Htotal, HCoI, Wkmax, Hmax])