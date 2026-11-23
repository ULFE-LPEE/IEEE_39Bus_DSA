'''
Author: Matjaz Skrlec
date: 07. 10. 2024
version: 1.0
description: This module is used for creating the undef freaquency load shedding (LFDD) scheme currently used by most
ENTSTO-e TSOs.
'''

#--------------------------------------------------------------------------------------------------
# imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
import logging

# support functions
def CheckIfDSLELmExists(name: str, grid, iprint: bool):
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

def CheckIfDSLTypExists(name: str, folder, iprint: bool):
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

def CreateTrigBlkTyp(name: str, folder, trigFreq: float, LodRed: float):
    '''
    This function creates the dynamic model typ which triggers the load decresing event.
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactors.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of Class IntPrjFolder or IntFolder"
    assert(type(trigFreq) in [int, float]), "Argument 'trigFreq' is not of type int or float"
    assert(type(LodRed) in [int, float]), "Argument 'LodRed' is not of type int or float"

    exist_bool, typ = CheckIfDSLTypExists(name, folder, False)
        
    if exist_bool:    
        print(f"Given DSL type name {name} already exists in given folder, not creating new DSL type")
        logging.info(f"Given DSL type name {name} already exists in given folder, not creating new DSL type")
        return(typ)

    equation_list =["inc(freq) = 1",\
                    "inc(trig_evt) = -1",\
                    "inc(trig_create) = -1",\
                    "trig_evt = select(freq <"+str(trigFreq)+", 1, -1)",\
                    "event(1, trig_evt, 'name=this value=1 variable=trig_create')",\
                    "event(1, trig_create, 'create=EvtLod target=LoadSlot name=LodDsl dP="+str(LodRed)+"')"]
    
    TrigBlkTyp = folder.CreateObject("BlkDef", name)
    TrigBlkTyp.SetAttribute("sInput",["freq"])
    TrigBlkTyp.SetAttribute("sAddEquat", equation_list)

    return(TrigBlkTyp)

def CreateCompBlkTyp(name: str, folder, trigFreq: float, LodRed: float):
    '''
    This function creates the composite model type.
    '''

    assert(type(name) == str), "Argument name is not of type str"
    assert(type(folder) == pf.DataObject), "Argument folder is not of type powerfactors.DataObject"
    assert(folder.GetClassName() in ["IntPrjfolder", "IntFolder"]), "Argument folder is not of Class IntPrjFolder or IntFolder"
    assert(type(trigFreq) in [int, float]), "Argument 'trigFreq' is not of type int or float"
    assert(type(LodRed) in [int, float]), "Argument 'LodRed' is not of type int or float"

    exist_bool, typCom = CheckIfDSLTypExists(name, folder, False)

    if exist_bool:
        exist_bool, typBlk = CheckIfDSLTypExists(name+"Trig", folder, False)
        print(f"Given DSL type with name {name+"Trig"} already exists in given folder, not creating new DSL type")
        logging.info(f"Given DSL type with name {name+"Trig"} already exists in given folder, not creating new DSL type")
        return(typCom, typBlk)

    CompBlkTyp = folder.CreateObject("BlkDef", name)
    TrigBlkTyp = CreateTrigBlkTyp(name+"Trig", folder, trigFreq, LodRed)

    FreqSlot = CompBlkTyp.CreateObject("BlkSlot", "FreqMeas")
    FreqSlot.SetAttribute("sOutput", ["fe"])
    TrigSlot = CompBlkTyp.CreateObject("BlkSlot", "TrigLogic")
    TrigSlot.SetAttribute("pDsl", TrigBlkTyp)
    LodSlot = CompBlkTyp.CreateObject("BlkSlot", "LoadSlot")

    freqSig = CompBlkTyp.CreateObject("BlkSig", "freq")
    freqSig.SetAttribute("pnodfrom", FreqSlot)
    freqSig.SetAttribute("inodfrom", 0)
    freqSig.SetAttribute("pnodto", TrigSlot)
    freqSig.SetAttribute("iconto", 1)
    freqSig.SetAttribute("inodto", 0)

    return CompBlkTyp, TrigBlkTyp 

def CreateTrigBlkElm(name: str, CompModel, TrigBlkTyp):
    '''
    This function creates a dynamic model element which triggers the load decreasing event. The dynamic
    model is created in the given composite model
    '''

    assert(type(name) == str), "Argument 'name' is not of type str"
    assert(type(CompModel) == pf.DataObject), "Argument 'CompModel' is not of type powerfactory.DataObject"
    assert(CompModel.GetClassName() == "ElmComp"), "Argument 'CompModel' is not of class 'ElmComp'"
    assert(type(TrigBlkTyp) == pf.DataObject), "Argument 'TrigBlkTyp' is not of type powerfactory.DataObject"
    assert(TrigBlkTyp.GetClassName() == "BlkDef"), "Argument 'TrigBlkTyp' is not of class 'BlkDef'"

    TrigBlkElm = CompModel.CreateObject("ElmDsl", name)
    TrigBlkElm.SetAttribute("typ_id", TrigBlkTyp)

    return(TrigBlkElm)

def CreateLFDDCompElm(name: str, CompBlkTyp, TrigBlkTyp, grid, Lod):
    '''
    This function creates a composite model which triggers LFDD on the given load at the given frequency level
    '''

    assert(type(name) == str), "Argument 'name' is not of type string"
    assert(type(CompBlkTyp) == pf.DataObject), "Argument 'CompBlkTyp' is not of type powerfactory.DataObject"
    assert(CompBlkTyp.GetClassName() == "BlkDef"), "Argument 'CompBlkTyp' is not of type powerfactory.DataObject"
    assert(type(TrigBlkTyp) == pf.DataObject), "Argument 'TrigBlkTyp' is not of type powerfactory.DataObject"
    assert(TrigBlkTyp.GetClassName() == "BlkDef"), "Argument 'TrigBlkTyp' is not of class 'BlkDef"
    assert(type(grid) == pf.DataObject), "Argument 'grid' is not of type powerfactory.DataObject"
    assert(grid.GetClassName() in ["ElmNet", "IntFolder"]), "Argument 'grid' should be of class 'ElmNet' or 'IntFolder'"
    assert(type(Lod) == pf.DataObject), "Argument 'Lod' is not of type powerfactory.DataObject"
    assert(Lod.GetClassName() == "ElmLod"), "Argument 'Lod' should be of class 'ElmLod'"

    exist_bool, Com = CheckIfDSLELmExists(name, grid, False)

    if exist_bool:
        print(f"Given composite model {name} element already exists, not creating a new composite model element")
        logging.info(f"Given composite model {name} element already exists, not creating a new composite model element")
        return(Com)

    LFDDCompElm = grid.CreateObject("ElmComp", name)
    LFDDCompElm.SetAttribute("typ_id", CompBlkTyp)

    LFDDBlkElm = LFDDCompElm.CreateObject("ElmDsl", "LFDDlogic")
    LFDDBlkElm.SetAttribute("typ_id", TrigBlkTyp)

    LodTerm = Lod.GetConnectedElements(1,1,1)[0]

    LFDDVMeas = LFDDCompElm.CreateObject("StaVmea","Vmea"+Lod.GetAttribute("loc_name"))
    LFDDVMeas.SetAttribute("pbusbar",LodTerm)

    pelm_list = [LFDDVMeas, LFDDBlkElm, Lod]

    LFDDCompElm.SetAttribute("pelm", pelm_list)

    return(LFDDCompElm)

# main functions

def CreateLFDDScheme(gridFolder, dynFolder, sLod: list, StagesFreq: tuple, StagesShed: tuple):
    '''
    This function creates a full under frequency load shedding scheme. The stages are defined with the 'StagesFreq' and 'StagesShed'
    lists. The sLod list defines which loads are affected by the sedding scheme.
    '''

    assert(type(gridFolder) == pf.DataObject), "Argument 'gridFolder' is not of type powerfactory.DataObject"
    assert(gridFolder.GetClassName() == "IntFolder"), "Argument 'gridFolder' is not of class 'IntFolder'"
    assert(type(dynFolder) == pf.DataObject), "Argument 'dynFodler' is not of type powerfactory.DataObject"
    assert(dynFolder.GetClassName() in ["IntFolder", "IntPrjfolder"]), "Argument 'dynFolder' is not of class 'IntFolder' or 'IntPrjFolder'"
    assert(type(sLod) == list), "Argument 'sLod' is not of type list"
    for i in range(len(sLod)):
        assert(type(sLod[i]) == pf.DataObject), "Argument sLod["+str(i)+"] is not of type powerfactory.DataObject"
        assert(sLod[i].GetClassName() == "ElmLod"), "Argument sLod ["+str(i)+"] is not of class 'ElmLod'"
    assert(type(StagesFreq) == tuple), "Argument 'StagesFreq' is not of type list"
    assert(type(StagesShed) == tuple), "Argument 'StagesShed' is not of type list"
    assert(len(StagesFreq) == len(StagesShed)), "Arguments 'StagesFreq' and 'StagesShed' are of different lengths"
    for i in range(len(StagesFreq)):
        assert(type(StagesFreq[i]) in [int, float]), "Argument StagesFreq["+str(i)+"] is not of type int of float"
        assert(type(StagesShed[i]) in [int, float]), "Argument StagesShed["+str(i)+"] is not of type int of float"
    
    LFDDBlkTyps = []
    LFDDFolders = []
    for i in range(len(StagesFreq)):
        currComTyp, currBlkTyp = CreateCompBlkTyp("LFDDStage"+str(i+1), dynFolder, StagesFreq[i], StagesShed[i])
        currLFDDFolder = gridFolder.CreateObject("intFolder", "LFDDStage"+str(i+1))    
        for j in sLod:
            if not j.GetConnectedElements(1,1,1):
                LodName = j.GetAttribute("loc_name")
                print("Load %s is not connected to the grid and will be ignored in LFDD." % (LodName))
                logging.info("Load %s is not connected to the grid and will be ignored in LFDD." % (LodName))
                continue 
            CreateLFDDCompElm("LFDD_Stage"+str(i+1)+"_"+j.GetAttribute("loc_name"), currComTyp, currBlkTyp, currLFDDFolder, j)
        LFDDBlkTyps.append(currComTyp)
        LFDDBlkTyps.append(currBlkTyp)
        LFDDFolders.append(currLFDDFolder)
    return(LFDDBlkTyps, LFDDFolders)