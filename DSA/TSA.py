'''
Author: Matjaz Skrlec
date: 30. 09. 2024
version: 1.0
description: This module is used for Transient stability assessment using powerfactory.
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
from typing import List, Tuple
import DSA.OutOfStep as OutOfStep
import DSA.HandleFiles as HandleFiles
import PFSupport.Utils
import PFSupport.GetElements as GetElements
import tqdm
import logging
import pandas as pd
import time
# support functions
def ExtractForName(ForName: str):
    forIndex = ForName.find(":")
    if forIndex:
        ForName = ForName[forIndex+1:]
    return ForName

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

def getTermForNameLst(FilePath: str, colName: str) -> list:
    TermDF = pd.read_excel(FilePath, sheet_name="Terminals")
    return(TermDF[colName].to_list())

def checkIfTermInList(TermID: str, TermWhiteList: list) -> bool:
    for ID in TermWhiteList:
        if TermID in ID:
            return(True)
        if ID in TermID:
            return(True)
        
    return(False)

def setUserParams(oComInc, oComSim, tStartTSA: float, tStopTSA: float, tSimStepTSA: float):
    '''
    The funciton for setting parameters of the simulation during transient stability assessment.
    '''

    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."
    assert(oComSim.GetClassName() == "ComSim"), "Given Argument 'oComSim' is not of type 'ComSim'."

    assert(type(tStartTSA) in [int, float]), "Given Argument 'tStartTSA' is not of type int or float."
    assert(type(tStopTSA) in [int, float]), "Given Argument 'tStopTSA' is not of type int or float."
    assert(type(tSimStepTSA) in [int,float]), "Given Argument 'tSimStopTSA' is not of type int or float."

    assert(tStartTSA <= 0), "Simulation start time ('tStartTSA') has to be shorter or equal to 0!"
    assert(tStopTSA > tStartTSA), "Simlation stop time ('tStopTSA') has to be longer than simulation start time ('tStartTSA')!"

    dtModifier = GetdtUnitModifier(oComInc)

    # Get initial simulation setup
    SimInitSetup = []

    SimInitSetup.append(oComInc.iopt_simscn)
    SimInitSetup.append(oComInc.iopt_sample)
    SimInitSetup.append(oComInc.tstart)
    SimInitSetup.append(oComInc.dtgrd)
    SimInitSetup.append(oComInc.iopt_locref)
    SimInitSetup.append(oComSim.tstop)

    # Set new simulation setup
    oComInc.iopt_simscn = 0
    oComInc.iopt_sample = 0
    oComInc.tstart = tStartTSA
    oComInc.dtgrd = tSimStepTSA*dtModifier
    oComInc.iopt_loref = 1
    oComSim.tstop = tStopTSA
    oComInc.automaticCompilation = 0

    return(SimInitSetup)

def setInitialParams(oComInc, oComSim, SimInitSetup):
    '''
    The function for setting simulaiton paramaters after transient stability assessment.
    '''

    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."
    assert(oComSim.GetClassName() == "ComSim"), "Given Argument 'oComSim' is not of type 'ComSim'."

    assert(type(SimInitSetup) == list), "Given Argument 'SimInitSetup' is not of type list."
    assert(len(SimInitSetup) == 6), "Given list 'SimInitSetup' is not of length 6."

    oComInc.iopt_simscn = SimInitSetup[0]
    oComInc.iopt_sample = SimInitSetup[1]
    oComInc.tstart = SimInitSetup[2]
    oComInc.dtgrd = SimInitSetup[3]
    oComInc.iopt_loref = SimInitSetup[4]
    oComSim.tstop = SimInitSetup[5]

    return(True)

def setupSimEvents(oComInc):
    '''
    This function sets up the required events needed for transient stability assessment.
    '''

    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."

    # put the original events out of service and store the original value of the event
    EvtInitSetup = []
    oEvent = oComInc.p_event
    sEvents = oEvent.GetContents()
    for oEvt in sEvents:
        EvtInitSetup.append([oEvt,oEvt.GetAttribute("outserv")])
        oEvt.SetAttribute("outserv", 1)

    # check and add short circuit event on terminal if necessary#
    oScOn = oEvent.CreateObject('EvtShc', "SC_on_Term_on")
    oScOff = oEvent.CreateObject('EvtShc', "Sc_on_Term_off")
    oSwLineOff = oEvent.CreateObject('EvtSwitch',"Sw_line_off")

    oScOn.SetAttribute("outserv", 0)
    oScOff.SetAttribute("outserv", 0)
    oScOff.SetAttribute("i_shc", 4)
    oScOn.SetAttribute("time", 0)
    oSwLineOff.SetAttribute("outserv", 1)
    oSwLineOff.SetAttribute("i_switch", 0)

    return(oScOn,oScOff,oSwLineOff,EvtInitSetup)

def setInitialEvents(oComReset, oScOn,oScOff, oSwLineOff, EvtInitSetup):

    assert(oComReset.GetClassName() == "ComReset"), "Given Argument 'oComReset' is not of type 'ComReset'."
    assert(oScOn.GetClassName() == "EvtShc"), "Argument 'oScOn' is not a short circuit event in Powerfactory."
    assert(oScOff.GetClassName() == "EvtShc"), "Argument 'oScOn' is not a short circuit event in Powerfactory."
    assert(oSwLineOff.GetClassName() == "EvtSwitch"), "Argument 'oSwLineOff' is not a switch event in Powerfactory."
    
    assert(type(EvtInitSetup) == list), "Argument 'EvtInitSetup' is not a list."

    oComReset.Execute()

    oScOn.Delete()
    oScOff.Delete()
    oSwLineOff.Delete()

    for oEvt in EvtInitSetup:
        oEvt[0].SetAttribute("outserv",oEvt[1])

    return (True)

def getGenBus(sGensAll):
    '''
    This function returns a list of all terminals next to the given generators. If the terminal is connected to a transformer,
    the terminal on the other side of the transformer is considered instead.
    '''

    assert(type(sGensAll) == list), "Given Argument 'sGensAll' is not of the type list."
    for i in sGensAll:
        assert(i.GetClassName() == 'ElmSym'), "An element in the list 'sGensAll' is not a synchronous machine."


    ScTerminals = []
    for oGen in sGensAll:
        sGenConElm = oGen.GetConnectedElements(1,1,1)
        for oGenElm in sGenConElm:
            sTier1Term = []
            sTier2Term = []
            sTier3Term = []
            sTier4Term = []
            sTier1Switches = []
            sTier2Switches = []
            sTermTransformers = []
            # get terminals directly at generators
            if (oGenElm.GetClassName() == 'ElmTerm'):
                sTier1Term.append(oGenElm)
                sTier1TermConElm = oGenElm.GetConnectedElements(1,1,1)

                for oTier1TermElm in sTier1TermConElm:
                    # check if the terminal is connected to a switch
                    if (oTier1TermElm.GetClassName() == 'ElmCoup'):
                        # if they are closed, consider them
                        if oTier1TermElm.GetAttribute("on_off") == 1:
                            sTier1Switches.append((oGenElm,oTier1TermElm))
                    # check if the terminal is connected to a transformer
                    if oTier1TermElm.GetClassName() == "ElmTr2":
                        sTermTransformers.append((oGenElm,oTier1TermElm))

                # Get Elements on the other side of the switches:
                if sTier1Switches:
                    SwitchOtherSideElm = []
                    for oSwitch in sTier1Switches:
                        SwitchOtherSideElm += (GetCoupOtherSide(oSwitch[1],oSwitch[0]))
                    # Check the elements on the other side are terminals
                    for oElm in SwitchOtherSideElm:
                        # if so, save them in the Tier 2 list
                        if oElm.GetClassName() == "ElmTerm":
                            sTier2Term.append(oElm)
                # check if tier 2 Terminals are connected to transformers
                for oTier2Term in sTier2Term:
                    for oTier2TermElm in oTier2Term.GetConnectedElements(1,1,1):
                        if oTier2TermElm.GetClassName() == "ElmTr2":
                            sTermTransformers.append((oTier2Term,oTier2TermElm))

                # for all transformers get the HV side busses and append them to the HV side
                for oTermTransformers in sTermTransformers:
                    CurrLVTerm = oTermTransformers[0]
                    CurrTR = oTermTransformers[1]
                    for oCurrTRElm in CurrTR.GetConnectedElements(1,1,1):
                        if oCurrTRElm.GetClassName() == "ElmTerm" and oCurrTRElm != CurrLVTerm:
                            sTier3Term.append(oCurrTRElm)
                
                # Check if the Terminals are connected to Couplers
                for oTier3Term in sTier3Term:
                    for oTier3TermElm in oTier3Term.GetConnectedElements(1,1,1):
                        if oTier3TermElm.GetClassName() == "ElmCoup":
                            if oTier3TermElm.GetAttribute("on_off") == 1:
                                sTier2Switches.append((oTier3Term,oTier3TermElm))
                
                # Get Elements on the other side of the switches:
                if sTier2Switches:
                    SwitchOtherSideElm = []
                    for oSwitch in sTier2Switches:
                        SwitchOtherSideElm += (GetCoupOtherSide(oSwitch[1],oSwitch[0]))
                    # Check the elements on the other side are terminals
                    for oElm in SwitchOtherSideElm:
                        # if so, save them in the Tier 4 list
                        if oElm.GetClassName() == "ElmTerm":
                            sTier4Term.append(oElm)
                
                sTermTiers = [sTier4Term, sTier3Term, sTier2Term, sTier1Term]
                for oTermTier in sTermTiers:
                    if oTermTier:
                        ScTerminals.append(oTermTier)
                        break

    return(ScTerminals)

def CheckIfTermOnMultLne(oTerm, contingencyGrids, LneList = None, ConsideredTerm = None):
    '''
    This function checks if a terminal is connected to multiple lines. It returns True if it is and False if it isn't. It also returns a list of the connected lines.
    '''
    assert(type(oTerm) == pf.DataObject), "Given Argument 'oTerm' is not type Powerfactory.dataobject."
    assert(oTerm.GetClassName() == "ElmTerm"), "Given Argument 'oTerm' is not of class 'ElmTerm'."
    assert(type(contingencyGrids) == list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) == pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"


    if not LneList:
        LneList = []
    if not ConsideredTerm:
        ConsideredTerm = []
    ConsideredTerm.append(oTerm)

    for oTermElm in oTerm.GetConnectedElements(1,1,1):
        if oTermElm.GetClassName() == "ElmLne":
            if oTermElm.GetAttribute("cpGrid") in contingencyGrids:
                LneList.append(oTermElm)
        if oTermElm.GetClassName() == "ElmCoup":
            if oTermElm.GetAttribute("on_off") == 1:
                for oCoupElm in oTermElm.GetConnectedElements(1,1,1,):
                    if oCoupElm.GetClassName() == "ElmTerm":
                        if not oCoupElm in ConsideredTerm:
                            index, LneList, ConsideredTerm = CheckIfTermOnMultLne(oCoupElm, contingencyGrids, LneList, ConsideredTerm)
        if oTermElm.GetClassName() == "ElmTerm":
            if not oTermElm in ConsideredTerm:
                index, LneList, ConsideredTerm = CheckIfTermOnMultLne(oTermElm, contingencyGrids, LneList, ConsideredTerm)

    if len(LneList) > 1:
        return(True, LneList, ConsideredTerm)
    return(False, LneList, ConsideredTerm)

def CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder):
    sGenAct = GetElements.GetElements(app, "ElmSym", [["outserv", 0]])
    
    sGenAng= []
    sAng = []
    for i in sGenAct:
        currComAngFrm = OutOfStep.CreateComAng("AngleAdder_"+str(i.GetAttribute("loc_name")), AngAdd_fold, ComElm_folder, i)
        sGenAng.append([i, currComAngFrm])
        if i in sGenRecord:
            sAng.append(currComAngFrm)

    return(sGenAng, sAng)

def TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDet, oTerm, tmin: float, tmax: float, epsilon: float, sGenAng: list, iprint: bool):
    '''
    This function calculates the critical clearing time of a three phase short circuit on a terminal and return the generator that is critical.
    '''

    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."
    assert(oComSim.GetClassName() == "ComSim"), "Given Argument 'oComSim' is not of type 'ComSim'."
    assert(oScOn.GetClassName() == "EvtShc"), "Argument 'oScOn' is not a short circuit event in Powerfactory."
    assert(oScOff.GetClassName() == "EvtShc"), "Argument 'oScOff' is not a short circuit event in Powerfactory."
    assert(OOSDet.GetClassName() == "ElmComp"), "Given Argument 'OOSDet' is not of type 'ElmComp'."
    assert(oTerm.GetClassName() == "ElmTerm"), "Given Argument 'oTerm' is not of type 'ElmTerm'."
    assert(type(tmin) in [int, float]), "Given Argument 'tmin' is not of type int or float."
    assert(type(tmax) in [int, float]), "Given Argument 'tmax' is not of type int or float."
    assert(type(epsilon) in [int, float]), "Given Argument 'epsilon' is not of type int or float."
    assert(type(sGenAng) == list), "Given Argument 'sGensAng' is not of type list."
    assert(type(iprint) == bool), "Given Argument 'iprint' is not of type bool."

    assert(tmin < tmax), "Minimum fualt clearing time ('tmin') has to be lower than maximum fault clearing time ('tmax')."

    assert(OOSDet.GetAttribute("outserv") == 0), "Out of step detection block is not active. Can't detect critical generator."

    # calculate precision for rounding
    precision = len(str(epsilon).split(".")[1])+1

    # Get actual OOS detection block
    for i in OOSDet.GetContents():
        if i.GetAttribute("loc_name") == "OOSDetBlk":
            OOSDetBlk = i

    # print start
    if (iprint):
        print("------------------------------------------------------------------------")
        print("------------------------------------------------------------------------")
        print("Starting CCT calculation for terminal "+oTerm.GetAttribute("loc_name")+".")
        logging.info("------------------------------------------------------------------------")
        logging.info("------------------------------------------------------------------------")
        logging.info("Starting CCT calculation for terminal "+oTerm.GetAttribute("loc_name")+".")

    # assert that the system is unstable for maximum CCT
    tclear = tmax
    oScOff.time = round(tclear,precision)

    iComInc = oComInc.Execute()
    iComSim = oComSim.Execute()
    if not (iComInc == 0 and iComSim == 0):
        print("There was an Error running initial condition or simulation. Disregarding this terminal.")
        logging.warning("There was an Error running initial condition or simulation. Disregarding terminal %s." % (oTerm.loc_name))
        return([1, 0, 0])

    stab_index = CheckStability(app, OOSDetBlk, sGenAng)
    if stab_index[0]:
        print("The system is stable for CCT %f (maximum CCT), at terminal %s." % (tclear, oTerm.loc_name))
        logging.info("The system is stable for CCT %f (maximum CCT), at terminal %s." % (tclear, oTerm.loc_name))
        return [0, tclear, stab_index[1]]
    tu = tclear


    # assert that system is stable for minimum CCT
    tclear = tmin
    oScOff.time = round(tclear,precision)

    iComInc = oComInc.Execute()
    iComSim = oComSim.Execute()
    if not (iComInc == 0 and iComSim == 0):
        print("There was an Error running initial condition or simulation. Disregarding this terminal.")
        logging.warning("There was an Error running initial condition or simulation. Disregarding terminal %s." % (oTerm.loc_name))
        return([1, tclear, 0])

    stab_index = CheckStability(app, OOSDetBlk, sGenAng)
    
    if not stab_index[0]:
        print('The system is unstable for CCT %f (minimum CCT), at terminal %s.' % (tclear, oTerm.loc_name))
        logging.info('The system is unstable for CCT %f (minimum CCT), at terminal %s.' % (tclear, oTerm.loc_name))
        return [0, tclear, stab_index[1]]
    ts = tclear


    # Calculate CCT
    iter = 0

    while((tu-ts) > epsilon):
        iter += 1
        tclear = (ts + tu) / 2
        oScOff.time = round(tclear,precision)
        iComInc = oComInc.Execute()
        iComSim = oComSim.Execute()
        if not (iComInc == 0 and iComSim == 0):
            print("There was an Error running initial condition or simulation. Disregarding this terminal.")
            logging.warning("There was an Error running initial condition or simulation. Disregarding terminal %s." % (oTerm.loc_name))
            return([1, tclear, 0])

        stab_index = CheckStability(app, OOSDetBlk, sGenAng)

        if (stab_index[0]):
            if (iprint):
                print('Iteration %i for clearing time of %f s. System was stable.' % (iter, tclear))
                logging.info('Iteration %i for clearing time of %f s. System was stable.' % (iter, tclear))
            ts = tclear
        else:
            if (iprint):
                print('Iteration %i for clearing time of %f s. System was unstable.' % (iter, tclear))
                print('Critical generator was %s.' % (stab_index[1].loc_name))
                logging.info('Iteration %i for clearing time of %f s. System was unstable.' % (iter, tclear))
                logging.info('Critical generator was %s.' % (stab_index[1].loc_name))
            oGenOut = stab_index[1]
            tu = tclear
    
    CCT = [0, ts, oGenOut]

    if(iprint):
        print('------------------')
        print('Critical fault Clearing Time for contingency at %s: %f s.' % (oTerm.loc_name, ts))
        print('Critical Generator was %s.' % (CCT[2].loc_name))
        logging.info('------------------')
        logging.info('Critical fault Clearing Time for contingency at %s: %f s.' % (oTerm.loc_name, ts))
        logging.info('Critical Generator was %s.' % (CCT[2].loc_name))
    return CCT

def LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDet, oLne, tmin: float, tmax: float, epsilon: float, sGenAng: list, iprint: bool):
    '''
    This function calculates the critical clearing time of a three phase short circuit on a line and return the generator that is critical.
    '''

    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."
    assert(oComSim.GetClassName() == "ComSim"), "Given Argument 'oComSim' is not of type 'ComSim'."
    assert(oScOn.GetClassName() == "EvtShc"), "Argument 'oScOn' is not a short circuit event in Powerfactory."
    assert(oLneOff.GetClassName() == "EvtSwitch"), "Argument 'oLneOff' is not a switch event in Powerfactory."
    assert(OOSDet.GetClassName() == "ElmComp"), "Given Argument 'OOSDet' is not of type 'ElmComp'."
    assert(oLne.GetClassName() == "ElmLne"), "Given Argument 'oLne' is not of type 'ElmLne'."
    assert(type(tmin) in [int, float]), "Given Argument 'tmin' is not of type int or float."
    assert(type(tmax) in [int, float]), "Given Argument 'tmax' is not of type int or float."
    assert(type(epsilon) in [int, float]), "Given Argument 'epsilon' is not of type int or float."
    assert(type(sGenAng) == list), "Given Argument 'sGensAng' is not of type list."
    assert(type(iprint) == bool), "Given Argument 'iprint' is not of type bool."

    assert(tmin < tmax), "Minimum fualt clearing time ('tmin') has to be lower than maximum fault clearing time ('tmax')."

    assert(OOSDet.GetAttribute("outserv") == 0), "Out of step detection block is not active. Can't detect critical generator."

    # calculate necessary precision for numbers
    precision = len(str(epsilon).split(".")[1])+1

    # Get actual OOS detection block
    for i in OOSDet.GetContents():
        if i.GetAttribute("loc_name") == "OOSDetBlk":
            OOSDetBlk = i

    # print start
    if (iprint):
        print("------------------------------------------------------------------------")
        print("------------------------------------------------------------------------")
        print("Starting CCT calculation for line %s." % (oLne.loc_name))
        logging.info("------------------------------------------------------------------------")
        logging.info("------------------------------------------------------------------------")
        logging.info("Starting CCT calculation for line %s." % (oLne.loc_name))

    # assert that the system is unstable for maximum CCTS
    time_sim_start = time.time()
    tclear = tmax
    oLneOff.time = round(tclear,precision)

    iComInc = oComInc.Execute()
    iComSim = oComSim.Execute()
    if not (iComInc == 0 and iComSim == 0):
        print("There was an Error running initial condition or simulation. Disregarding this line.")
        logging.warning("There was an Error running initial condition or simulation. Disregarding line %s." % (oLne.loc_name))
        return([1, 0, 0])

    stab_index = CheckStability(app, OOSDetBlk, sGenAng)
    logging.info(f"Simulation time for clearing time {tclear}, {time.time()-time_sim_start}")

    if stab_index[0]:
        print("The system is stable for CCT %f (maximum CCT), at line %s." % (tclear, oLne.loc_name))
        logging.info("The system is stable for CCT %f (maximum CCT), at line %s." % (tclear, oLne.loc_name))
        return [0, tclear, stab_index[1]]
    tu = tclear

    # assert that system is stable for minimum CCT
    
    time_sim_start = time.time()
    tclear = tmin
    oLneOff.time = round(tclear,precision)

    iComInc = oComInc.Execute()
    iComSim = oComSim.Execute()
    if not (iComInc == 0 and iComSim == 0):
        print("There was an Error running initial condition or simulation. Disregarding this line.")
        logging.warning("There was an Error running initial condition or simulation. Disregarding line %s." % (oLne.loc_name))
        return([1, tclear, 0])

    stab_index = CheckStability(app, OOSDetBlk, sGenAng)
    logging.info(f"Simulation time for clearing time {tclear}, {time.time()-time_sim_start}")

    if not stab_index[0]:
        print("The system is unstable for CCT %f (minimum CCT), at line %s." % (tclear, oLne.loc_name))
        logging.info("The system is unstable for CCT %f (minimum CCT), at line %s." % (tclear, oLne.loc_name))
        return [0, tclear, stab_index[1]]
    ts = tclear

    # Calculate CCT
    iter = 0

    while((tu - ts) > epsilon):
        time_sim_start = time.time()
        iter += 1
        tclear = (ts + tu) / 2
        oLneOff.time = round(tclear,precision)
        
        iComInc = oComInc.Execute()
        iComSim = oComSim.Execute()
        if not (iComInc == 0 and iComSim == 0):
            print("There was an Error running initial condition or simulation. Disregarding this line.")
            logging.warning("There was an Error running initial condition or simulation. Disregarding line %s." % (oLne.loc_name))
            return([1, tclear, 0])

        stab_index = CheckStability(app, OOSDetBlk, sGenAng)
        logging.info(f"Simulation time for clearing time {tclear}, {time.time()-time_sim_start}")

        if (stab_index[0]):
            if(iprint):
                print("Iteration %i for clearing time of %f s. System was stable." % (iter, tclear))
                logging.info("Iteration %i for clearing time of %f s. System was stable." % (iter, tclear))
            ts = tclear
        else:
            if(iprint):
                print("Iteration %i for clearing time of %f s. System was unstable." % (iter, tclear))
                print("Critical generator was %s." % (stab_index[1].loc_name))
                logging.info("Iteration %i for clearing time of %f s. System was unstable." % (iter, tclear))
                logging.info("Critical generator was %s." % (stab_index[1].loc_name))
            oGenOut = stab_index[1]
            tu = tclear


    CCT =[0, ts, oGenOut]

    if(iprint):
        print('------------------')
        print('Critical fault Clearing Time for contingency at %s: %f s.' % (oLne.loc_name, ts))
        print('Critical Generator was %s' % (CCT[2].loc_name))
        logging.info('------------------')
        logging.info('Critical fault Clearing Time for contingency at %s: %f s.' % (oLne.loc_name, ts))
        logging.info('Critical Generator was %s' % (CCT[2].loc_name))
    return CCT

def LneCCTv2(app, oComInc, oComSim, oScOn, oLneOff, OOSDet, oLne, tmin: float, tmax: float, epsilon: float, sGenAng: list, iprint: bool):
    '''
    This function calculates the critical clearing time of a three phase short circuit on a line and return the generator that is critical.
    '''

    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."
    assert(oComSim.GetClassName() == "ComSim"), "Given Argument 'oComSim' is not of type 'ComSim'."
    assert(oScOn.GetClassName() == "EvtShc"), "Argument 'oScOn' is not a short circuit event in Powerfactory."
    assert(oLneOff.GetClassName() == "EvtSwitch"), "Argument 'oLneOff' is not a switch event in Powerfactory."
    assert(OOSDet.GetClassName() == "ElmComp"), "Given Argument 'OOSDet' is not of type 'ElmComp'."
    assert(oLne.GetClassName() == "ElmLne"), "Given Argument 'oLne' is not of type 'ElmLne'."
    assert(type(tmin) in [int, float]), "Given Argument 'tmin' is not of type int or float."
    assert(type(tmax) in [int, float]), "Given Argument 'tmax' is not of type int or float."
    assert(type(epsilon) in [int, float]), "Given Argument 'epsilon' is not of type int or float."
    assert(type(sGenAng) == list), "Given Argument 'sGensAng' is not of type list."
    assert(type(iprint) == bool), "Given Argument 'iprint' is not of type bool."

    assert(tmin < tmax), "Minimum fualt clearing time ('tmin') has to be lower than maximum fault clearing time ('tmax')."

    assert(OOSDet.GetAttribute("outserv") == 0), "Out of step detection block is not active. Can't detect critical generator."

    # calculate precision for rounding
    precision = len(str(epsilon).split(".")[1])+1

    # Get actual OOS detection block
    for i in OOSDet.GetContents():
        if i.GetAttribute("loc_name") == "OOSDetBlk":
            OOSDetBlk = i

    # print start
    if (iprint):
        print("------------------------------------------------------------------------")
        print("------------------------------------------------------------------------")
        print("Starting CCT calculation for line %s." % (oLne.loc_name))
        logging.info("------------------------------------------------------------------------")
        logging.info("------------------------------------------------------------------------")
        logging.info("Starting CCT calculation for line %s." % (oLne.loc_name))

    # assert that the system is unstable for maximum CCT
    stab_check_upper = True
    tu_change_flag = False
    tclear = tmax
    while stab_check_upper:
        time_sim_start = time.time()
        oLneOff.time = round(tclear,precision)

        iComInc = oComInc.Execute()
        iComSim = oComSim.Execute()
        if not (iComInc == 0 and iComSim == 0):
            print("There was an Error running initial condition or simulation. Disregarding this line.")
            logging.warning("There was an Error running initial condition or simulation. Disregarding line %s." % (oLne.loc_name))
            return([1, 0, 0])

        stab_index = CheckStability(app, OOSDetBlk, sGenAng)
        stab_check_upper = stab_index[0]
        logging.info(f"Simulation time for clearing time {tclear}, {time.time()-time_sim_start}")
        if stab_index[0]:
            ts = tclear
            tu_change_flag = True
            tclear = tclear + 0.1
            if tclear > 1.9:
                print("The system is stable for CCT %f (maximum CCT), at line %s." % (tclear, oLne.loc_name))
                logging.info("The system is stable for CCT %f (maximum CCT), at line %s." % (tclear, oLne.loc_name))
                return [0, tclear, stab_index[1]]
        else:
            oGenOut = stab_index[1]
    tu = tclear
    # assert that system is stable for minimum CCT
    stab_check_lower = False
    tclear = tmin
    while not stab_check_lower and not tu_change_flag:
        time_sim_start = time.time()
        oLneOff.time = round(tclear,precision)

        iComInc = oComInc.Execute()
        iComSim = oComSim.Execute()
        if not (iComInc == 0 and iComSim == 0):
            print("There was an Error running initial condition or simulation. Disregarding this line.")
            logging.warning("There was an Error running initial condition or simulation. Disregarding line %s." % (oLne.loc_name))
            return([1, tclear, 0])

        stab_index = CheckStability(app, OOSDetBlk, sGenAng)
        stab_check_lower = stab_index[0]
        logging.info(f"Simulation time for clearing time {tclear}, {time.time()-time_sim_start}")
        if not stab_check_lower:
            tclear = tclear - 0.1
            if tclear < 0:
                print("The system is unstable for CCT %f (minimum CCT), at line %s." % (tclear, oLne.loc_name))
                logging.info("The system is unstable for CCT %f (minimum CCT), at line %s." % (tclear, oLne.loc_name))
                return [0, tclear, stab_index[1]]
    ts = tclear

    # Calculate CCT
    iter = 0

    while((tu - ts) > epsilon):
        time_sim_start = time.time()
        iter += 1
        tclear = (ts + tu) / 2
        oLneOff.time = round(tclear,precision)
        
        iComInc = oComInc.Execute()
        iComSim = oComSim.Execute()
        if not (iComInc == 0 and iComSim == 0):
            print("There was an Error running initial condition or simulation. Disregarding this line.")
            logging.warning("There was an Error running initial condition or simulation. Disregarding line %s." % (oLne.loc_name))
            return([1, tclear, 0])

        stab_index = CheckStability(app, OOSDetBlk, sGenAng)
        logging.info(f"Simulation time for clearing time {tclear}, {time.time()-time_sim_start}")
        if (stab_index[0]):
            if(iprint):
                print("Iteration %i for clearing time of %f s. System was stable." % (iter, tclear))
                logging.info("Iteration %i for clearing time of %f s. System was stable." % (iter, tclear))
            ts = tclear
        else:
            if(iprint):
                print("Iteration %i for clearing time of %f s. System was unstable." % (iter, tclear))
                print("Critical generator was %s." % (stab_index[1].loc_name))
                logging.info("Iteration %i for clearing time of %f s. System was unstable." % (iter, tclear))
                logging.info("Critical generator was %s." % (stab_index[1].loc_name))
            oGenOut = stab_index[1]
            tu = tclear
        

    CCT =[0, ts, oGenOut]

    if(iprint):
        print('------------------')
        print('Critical fault Clearing Time for contingency at %s: %f s.' % (oLne.loc_name, ts))
        print('Critical Generator was %s' % (CCT[2].loc_name))
        logging.info('------------------')
        logging.info('Critical fault Clearing Time for contingency at %s: %f s.' % (oLne.loc_name, ts))
        logging.info('Critical Generator was %s' % (CCT[2].loc_name))
    return CCT

def CheckStability(app, OOSDetBlk, sGenAng):
    '''
    This function checks, whether the system is stable after an RSM simulation. In case of an unstable system, the funciton also returns the
    critical machine, otherwise it returns a 0.
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(OOSDetBlk.GetClassName() == "ElmDsl"), "Given Argument 'OOSDetBlk' is not of type 'ElmDsl'"
    assert type(sGenAng) == list, "sGenAng is of type"+str(type(sGenAng))+", when it should be of type list."

    if OOSDetBlk.GetAttribute("c:ev_trig") == -1:
        return(True, 0)
    else:
        crit_machine = OutOfStep.DetectCritGenerator(app, sGenAng)
        return(False,crit_machine[0])

def setupStudyCases(sGenCCT: List[pf.DataObject], ComElm_folder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, settings: tuple,  iprint: bool) -> Tuple[List[pf.DataObject], List[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenCCT.

    The function takes the following arguments:\n
    :param sGenCCT: a list of generators for which to create study cases.\n
    :param ComElm_folder: The folder with the angle adder and out of step detection blocks.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: Tuple of settings for dynamic simulation.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(ComElm_folder) == pf.DataObject), "The Argument 'ComElm_folder' is not of type PowerFactory.DataObject."
    assert(type(studyCaseFolder) == pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) == str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) == pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(settings) == tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: List[pf.DataObject] = []
    createdComPython: List[pf.DataObject] = []
    
    # Create new StudyCase for each generator in sGenCCT
    for i, generator in enumerate(sGenCCT):
        studyCaseName = f'SC at generator {generator.GetAttribute("loc_name")}'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects
        DefineInput(comPythonObject, ComElm_folder, sGenCCT[i], settings)
        createdComPython.append(comPythonObject)
    
    return createdStudyCases, createdComPython

def setupStudyCasesTSAUntilTreshold(sGenCCT: List[pf.DataObject], ComElm_folder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, settings: list, contingencyGrids: list[pf.DataObject], iprint: bool) -> Tuple[List[pf.DataObject], List[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenCCT.

    The function takes the following arguments:\n
    :param sGenCCT: a list of generators for which to create study cases.\n
    :param ComElm_folder: The folder with the angle adder and out of step detection blocks.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: Tuple of settings for dynamic simulation.\n
    :param CCT_treshold: setting for when to stop searching for new elements to calculate CCTs.\n
    :param contingencyGrids: a list of grids in which contingencies should be considered.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(ComElm_folder) == pf.DataObject), "The Argument 'ComElm_folder' is not of type PowerFactory.DataObject."
    assert(type(studyCaseFolder) == pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) == str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) == pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(settings) == tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 8), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4] The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)\n\
                                - [6] The Threshold at which to stop searching for CCTs (in s)\n\
                                - [7] The number at which to stop coninue searching for further elements in grid."
    assert(type(contingencyGrids) == list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) == pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."
    createdStudyCases: List[pf.DataObject] = []
    createdComPython: List[pf.DataObject] = []
    
    # Create new StudyCase for each generator in sGenCCT
    for i, generator in enumerate(sGenCCT):
        studyCaseName = f'SC at generator {generator.GetAttribute("loc_name")}'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects
        DefineInputTSAUntilTreshold(comPythonObject, ComElm_folder, sGenCCT[i], contingencyGrids, settings)
        createdComPython.append(comPythonObject)
    
    return createdStudyCases, createdComPython

def ReadResFilesTSA(sGenCCT: List[pf.DataObject], tempResultsDir: str, ) -> list[list]:
    CCT_info_lists: List[List] = []
    for id, generator in enumerate(sGenCCT):
        generatorName = getForOrLocName(generator)
        if ":" in generatorName:
            index = generatorName.find(":")
            generatorName = generatorName[index+1:]
        file_indexing = 0
        tempFilePath = f"{tempResultsDir}\\cctInfo_{generatorName}_{file_indexing}.pkl"
        while os.path.exists(tempFilePath):
            try:
                cctResults = HandleFiles.loadResultsFromTemporaryFile(tempFilePath)
                if cctResults is not None:
                    CCT_info_lists.append(cctResults)
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
            tempFilePath = f"{tempResultsDir}\\cctInfo_{generatorName}_{file_indexing}.pkl"
    return(CCT_info_lists)

def RedefineToOriginalElements(app: pf.Application, CCT_info_lists: list[list]) -> list[list]:
    for index, CCT_info_list in enumerate(CCT_info_lists):
        original_term_ref = CCT_info_list[1]
        original_crit_gen_ref = CCT_info_list[2]
        original_fault_elm_ref = CCT_info_list[4]

        try:
            # Try to get the terminal object
            term_objects = app.GetCalcRelevantObjects(f"*{original_term_ref}")
            if term_objects: # Check if the list is not empty
                CCT_info_list[1] = term_objects[0]
                CCT_info_lists[index][1] = term_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_term_ref}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_term_ref}: {e}. Keeping original reference.")

        try:
            # Try to get the critical generator object
            crit_gen_objects = app.GetCalcRelevantObjects(f"*{original_crit_gen_ref}")
            if crit_gen_objects: # Check if the list is not empty
                CCT_info_list[2] = crit_gen_objects[0]
                CCT_info_lists[index][2] = crit_gen_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_crit_gen_ref}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_crit_gen_ref}: {e}. Keeping original reference.")

        try:
            # Try to get the fault element object
            fault_elm_objects = app.GetCalcRelevantObjects(f"*{original_fault_elm_ref}")
            if fault_elm_objects: # Check if the list is not empty
                CCT_info_list[4] = fault_elm_objects[0]
                CCT_info_lists[index][4] = fault_elm_objects[0]
            else:
                logging.warning(f"Could not find object for reference: {original_fault_elm_ref}. Keeping original reference.")
        except Exception as e:
            logging.error(f"Error getting object for reference {original_fault_elm_ref}: {e}. Keeping original reference.")

    return CCT_info_lists

def RedefineToOriginalElementsTSATreshold(app: pf.Application, whole_CCT_info_lists: list[list]) -> list[list]:
    for CCT_info_lists in whole_CCT_info_lists:
        for index, CCT_info_list in enumerate(CCT_info_lists):
            original_term_ref = CCT_info_list[1]
            original_crit_gen_ref = CCT_info_list[2]
            original_fault_elm_ref = CCT_info_list[4]

            try:
                # Try to get the terminal object
                term_objects = app.GetCalcRelevantObjects(f"*{original_term_ref}")
                if term_objects: # Check if the list is not empty
                    CCT_info_list[1] = term_objects[0]
                    CCT_info_lists[index][1] = term_objects[0]
                else:
                    logging.warning(f"Could not find object for reference: {original_term_ref}. Keeping original reference.")
            except Exception as e:
                logging.error(f"Error getting object for reference {original_term_ref}: {e}. Keeping original reference.")

            try:
                # Try to get the critical generator object
                crit_gen_objects = app.GetCalcRelevantObjects(f"*{original_crit_gen_ref}")
                if crit_gen_objects: # Check if the list is not empty
                    CCT_info_list[2] = crit_gen_objects[0]
                    CCT_info_lists[index][2] = crit_gen_objects[0]
                else:
                    logging.warning(f"Could not find object for reference: {original_crit_gen_ref}. Keeping original reference.")
            except Exception as e:
                logging.error(f"Error getting object for reference {original_crit_gen_ref}: {e}. Keeping original reference.")

            try:
                # Try to get the fault element object
                fault_elm_objects = app.GetCalcRelevantObjects(f"*{original_fault_elm_ref}")
                if fault_elm_objects: # Check if the list is not empty
                    CCT_info_list[4] = fault_elm_objects[0]
                    CCT_info_lists[index][4] = fault_elm_objects[0]
                else:
                    logging.warning(f"Could not find object for reference: {original_fault_elm_ref}. Keeping original reference.")
            except Exception as e:
                logging.error(f"Error getting object for reference {original_fault_elm_ref}: {e}. Keeping original reference.")

    return whole_CCT_info_lists

def CleanupTemp(tempResultsDir: str) -> bool:
    filepaths = [os.path.join(tempResultsDir, filename) for filename in os.listdir(tempResultsDir)]
    for filepath in filepaths:
        if "cctInfo_" in filepath:
            try:
                os.remove(filepath)
            except FileNotFoundError:
                logging.warning(f"Temporary file not found during cleanup, skipping removal: {filepath}")
            except OSError as e:
                logging.error(f"Error removing temporary file {filepath}: {e}")
            except Exception as e:
                logging.error(f"Unexpected error removing temporary file {filepath}: {e}")
    return True

def DefineInput(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, settings: list) -> bool:
    ParamTypeInputList = ["double", "double", "double", "double", "double", "double"]
    ParamNameInputList = ["tStartTSA", "tStopTSA", "tSimStepTSA", "tMaxClear", "tMinClear" ,"tStepTSA"]
    ParamValueInputList = list(map(lambda x: str(x), settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def DefineInputTSAUntilTreshold(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oGen: pf.DataObject, contingencyGrids: list[pf.DataObject], settings: list) -> bool:
    ParamTypeInputList = ["double", "double", "double", "double", "double", "double", "double", "int"]
    ParamNameInputList = ["tStartTSA", "tStopTSA", "tSimStepTSA", "tMaxClear", "tMinClear" ,"tStepTSA", "CCT_treshold", "nRecord"]
    ParamValueInputList = list(map(lambda x: str(x), settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    contingencyGridsNameList = []
    contingencyGridsObjectList = []
    for i, obj in enumerate(contingencyGrids):
        contingencyGridsNameList.append(f"ContingencyGrid_{i}")
        contingencyGridsObjectList.append(obj)
    comPythonObject.obj_name = ["generatorInput", "ComElm_folder"]+contingencyGridsNameList # type: ignore
    comPythonObject.obj_id = [oGen, ComElm_folder]+contingencyGridsObjectList # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def SetCurrVenvInScript(script_path: os.path, iprint:bool) -> bool:
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

def TSAForTermAtSingleGenerator(app: pf.Application, settings: list, OOSDetFrm: pf.DataObject, sGenAng: list, oGenCCT: pf.DataObject, iprint: bool):
    '''
    This function is meant to be called from external processing script.

    :param app: The powerfactory application in which the desired project should already be activated.\n
    :param settings: The desired settings list which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [5] The critical clearing time accuracy (in s)\n

    :param OOSDetFrm: The Out of step detection frame.\n
    :param sGenAng: a list of pf.DataObject that are used to measure generator rotor angles.\n
    :param sGenCCT: The generator near which SC contingency will be calculated.\n
    :param iprint: A boolean that determines if the results should be printed\n
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == list), "Given Argument 'settings' is not a list."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(OOSDetFrm) == pf.DataObject), "The Argument 'OOSDetFrm' is not of type 'Powerfactory.DataObject'"
    assert(type(sGenAng) == list), "The Argument 'sGenAng' is not of type 'list'"
    assert(type(oGenCCT) == pf.DataObject), "The Argument 'oGenCCT' is not of type Powerfactory.DataObject"
    assert(oGenCCT.GetClassName() == "ElmSym"), "The Argument 'oGenCCT' is not of class 'ElmSym'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    # Get terminal at generator
    ScTerms = getGenBus([oGenCCT])[0]

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)
    # Run CCT evaluation
    CCT_info_list = []
    CCT_Error_list = []

    logging.info(ScTerms)

    for oTerm in ScTerms:
        oScOn.p_target = oTerm
        oScOff.p_target = oTerm
        CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm, settings[4], settings[3], settings[2], sGenAng, iprint)
        CritGen = getForOrLocName(CCT_info[2])
        ScTermName = getForOrLocName(oTerm)
        output_list = [CCT_info[1], ScTermName, CritGen, 0, ScTermName]
        if CCT_info[0] == 0:
            if oGenCCT == CCT_info[2]:
                CCT_info_list.append(output_list)
        else:
            ScTermName = getForOrLocName(oTerm)
            CCT_Error_list.append([ScTermName, CCT_info[1]])

        
    # CCT_info_list = output_list # this is intruder

    # Reset initial settings 
    oComReset.Execute() # type: ignore
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()

    # Report errors
    if CCT_Error_list is not None:
        for Error in CCT_Error_list:
            print("Error occurred for simulation at %s for short circuit time %f s." % (Error[0], Error[1]))
            logging.error("Error occurred for simulation at %s for short circuit time %f s." % (Error[0], Error[1]))
    return (CCT_info_list)

def TSAForLine(app: pf.Application, settings: list, OOSDetFrm: pf.DataObject, sGenAng: list, oTerm: pf.DataObject, oLne: pf.DataObject, iprint: bool):
    '''
    This function is meant to be called from external processing script.

    :param app: The powerfactory application in which the desired project should already be activated.\n
    :param settings: The desired settings list which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [5] The critical clearing time accuracy (in s)\n

    :param OOSDetFrm: The Out of step detection frame.\n
    :param sGenAng: a list of pf.DataObject that are used to measure generator rotor angles.\n
    :param oTerm: The terminal near which the contingency will be calculated.\n
    :param oLne: The line on which the contingency will be calculated.\n
    :param iprint: A boolean that determines if the results should be printed\n
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == list), "Given Argument 'settings' is not a list."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(OOSDetFrm) == pf.DataObject), "The Argument 'OOSDetFrm' is not of type 'Powerfactory.DataObject'"
    assert(type(sGenAng) == list), "The Argument 'sGenAng' is not of type 'list'"
    assert(type(oTerm) == pf.DataObject), "The Argument 'oTerm' is not of type Powerfactory.DataObject"
    assert(oTerm.GetClassName() == "ElmTerm"), "TheArgument 'oTerm' is not of class 'ElmTerm'"
    assert(type(oLne) == pf.DataObject), "The Argument 'oLne' is not of type Powerfactory.DataObject"
    assert(oLne.GetClassName() == "ElmLne"), "The Argument 'oLne' is not of class 'ElmLne'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)
    oScOff.outserv = 1
    oLneOff.outserv = 0
    # Run CCT evaluation
    CCT_info_list = None
    CCT_Error_list = None
    
    oScOn.p_target = oLne
    oLneOff.p_target = oLne
    if oLne.GetAttribute("bus1").GetAttribute("cterm") == oTerm:
        oScOn.SetAttribute("shcLocation", 10)
    else:
        oScOn.SetAttribute("shcLocation", 90)
        
    CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne, settings[4], settings[3], settings[5], sGenAng, iprint)
    CritGen = getForOrLocName(CCT_info[2])
    ScTermName = getForOrLocName(oTerm)
    oLneName = getForOrLocName(oLne)
    output_list = [CCT_info[1], ScTermName, CritGen, 1, oLneName]
    if CCT_info[0] == 0:
        CCT_info_list = output_list
    else:
        CCT_Error_list = [oLneName, CCT_info[1]]

    # Reset initial settings 
    oComReset.Execute() # type: ignore
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()

    # Report errors
    if CCT_Error_list is not None:
        print("Error occurred for simulation at %s for short circuit time %f s." % (CCT_Error_list[0], CCT_Error_list[1]))
        logging.error("Error occurred for simulation at %s for short circuit time %f s." % (CCT_Error_list[0], CCT_Error_list[1]))
    return (CCT_info_list)

def TSAForLinev2(app: pf.Application, settings: list, OOSDetFrm: pf.DataObject, sGenAng: list, oTerm: pf.DataObject, oLne: pf.DataObject, iprint: bool):
    '''
    This function is meant to be called from external processing script.

    :param app: The powerfactory application in which the desired project should already be activated.\n
    :param settings: The desired settings list which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [5] The critical clearing time accuracy (in s)\n

    :param OOSDetFrm: The Out of step detection frame.\n
    :param sGenAng: a list of pf.DataObject that are used to measure generator rotor angles.\n
    :param oTerm: The terminal near which the contingency will be calculated.\n
    :param oLne: The line on which the contingency will be calculated.\n
    :param iprint: A boolean that determines if the results should be printed\n
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == list), "Given Argument 'settings' is not a list."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(OOSDetFrm) == pf.DataObject), "The Argument 'OOSDetFrm' is not of type 'Powerfactory.DataObject'"
    assert(type(sGenAng) == list), "The Argument 'sGenAng' is not of type 'list'"
    assert(type(oTerm) == pf.DataObject), "The Argument 'oTerm' is not of type Powerfactory.DataObject"
    assert(oTerm.GetClassName() == "ElmTerm"), "TheArgument 'oTerm' is not of class 'ElmTerm'"
    assert(type(oLne) == pf.DataObject), "The Argument 'oLne' is not of type Powerfactory.DataObject"
    assert(oLne.GetClassName() == "ElmLne"), "The Argument 'oLne' is not of class 'ElmLne'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)
    oScOff.outserv = 1
    oLneOff.outserv = 0
    # Run CCT evaluation
    CCT_info_list = None
    CCT_Error_list = None
    
    oScOn.p_target = oLne
    oLneOff.p_target = oLne
    if oLne.GetAttribute("bus1").GetAttribute("cterm") == oTerm:
        oScOn.SetAttribute("shcLocation", 10)
    else:
        oScOn.SetAttribute("shcLocation", 90)
        
    CCT_info = LneCCTv2(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne, settings[4], settings[3], settings[5], sGenAng, iprint)
    CritGen = getForOrLocName(CCT_info[2])
    ScTermName = getForOrLocName(oTerm)
    oLneName = getForOrLocName(oLne)
    output_list = [CCT_info[1], ScTermName, CritGen, 1, oLneName]
    if CCT_info[0] == 0:
        CCT_info_list = output_list
    else:
        CCT_Error_list = [oLneName, CCT_info[1]]

    # Reset initial settings 
    oComReset.Execute() # type: ignore
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()

    # Report errors
    if CCT_Error_list is not None:
        print("Error occurred for simulation at %s for short circuit time %f s." % (CCT_Error_list[0], CCT_Error_list[1]))
        logging.error("Error occurred for simulation at %s for short circuit time %f s." % (CCT_Error_list[0], CCT_Error_list[1]))
    return (CCT_info_list)

def TSAUntilTresholdSingleGenerator(app: pf.Application, settings: list, CCT_treshold: float, nRecord: int, OOSDetFrm: pf.DataObject, sGenAng: list, oGenCCT: pf.DataObject, contingencyGrids: list[pf.DataObject], iprint: bool):
    '''
    This function is meant to be called from external processing script.

    :param app: The powerfactory application in which the desired project should already be activated.\n
    :param settings: The desired settings list which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [5] The critical clearing time accuracy (in s)\n

    :param CCT_treshold: The treshold (in s) for when to stop continue CCT search.\n
    :param nRecord: The number of cases above which to stop analysing.\n
    :param OOSDetFrm: The Out of step detection frame.\n
    :param sGenAng: a list of pf.DataObject that are used to measure generator rotor angles.\n
    :param sGenCCT: The generator near which SC contingency will be calculated.\n
    :param contingencyGrids: a list of grids in which contingencies should be considered.\n
    :param iprint: A boolean that determines if the results should be printed\n
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == list), "Given Argument 'settings' is not a list."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(CCT_treshold < settings[3]), "The critical clearing treshold (CCT_treshold), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(nRecord) == int), "Givne Argumen 'nRecord' is not of type int."
    assert(type(OOSDetFrm) == pf.DataObject), "The Argument 'OOSDetFrm' is not of type 'Powerfactory.DataObject'"
    assert(type(sGenAng) == list), "The Argument 'sGenAng' is not of type 'list'"
    assert(type(oGenCCT) == pf.DataObject), "The Argument 'sGenCCT' is not of type Powerfactory.DataObject"
    assert(oGenCCT.GetClassName() == "ElmSym"), "The Argument 'sGenCCT' is not of class 'ElmSym'"
    assert(type(contingencyGrids) == list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) == pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    nCalculated = 0

    # Get terminal at generator
    ScTerm = getGenBus([oGenCCT])[0]

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)

    # Run CCT evaluation
    analysed_elements = []
    CCT_info_list = []
    CCT_Error_list = []

    DidBranch = False
    ContinueSearchTerms = []

    # Analyse fault on terminal closest to generator
    for oTerm in ScTerm:
        oScOn.p_target = oTerm
        oScOff.p_target = oTerm
        CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm, settings[4], settings[3], settings[2], sGenAng, iprint)
        nCalculated = nCalculated + 1
        if CCT_info[0] == 0:
            if oGenCCT == CCT_info[2]:
                oTermName = getForOrLocName(oTerm)
                CritGetName = getForOrLocName(CCT_info[2])
                output_list = [CCT_info[1], oTermName, CritGetName, 0, oTermName]
                CCT_info_list.append(output_list)
                analysed_elements.append(oTerm)
                if CCT_info[0] < CCT_treshold:
                    ContinueSearchTerms.append(oTerm)
            lne_check = CheckIfTermOnMultLne(oTerm, contingencyGrids)
        else:
            oTermName = getForOrLocName(oTerm)
            CCT_Error_list = [oTermName, CCT_info[1]]

        # If there is multiple lines analyse faults on those lines 
        if lne_check[0]:
            DidBranch = True
            oScOff.outserv = 1
            oLneOff.outserv = 0
            for oLne in lne_check[1]:
                oScOn.p_target = oLne
                oLneOff.p_target = oLne
                if oLne.GetAttribute("bus1").GetAttribute("cterm") == oTerm:
                    oScOn.SetAttribute("shcLocation", 10)
                else:
                    oScOn.SetAttribute("shcLocation", 90)
                CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne, settings[4], settings[3], settings[5], sGenAng, iprint)
                nCalculated = nCalculated + 1
                if CCT_info[0] == 0:
                    if oGenCCT == CCT_info[2]:
                        oTermName = getForOrLocName(oTerm)
                        CritGetName = getForOrLocName(CCT_info[2])
                        oLneName = getForOrLocName(oLne)
                        output_list = [CCT_info[1], oTermName, CritGetName, 1, oLneName]
                        CCT_info_list.append(output_list)
                        analysed_elements.append(oLne)
                else:
                    oLneName = getForOrLocName(oLne)
                    CCT_Error_list.append([oLneName, CCT_info[1]])
            oScOff.outserv = 0
            oLneOff.outserv = 1
        else:
            for oLne in lne_check[1]:
                analysed_elements.append(oLne)

    # while the terminal short circuit is smaller than the threshold
    while ContinueSearchTerms and (nCalculated <= nRecord):
        currentTerms = []

        oComReset.Execute()
        #Get Terminals to analyse
        for oTerm1 in ContinueSearchTerms:
            for oTermElm in oTerm1.GetConnectedElements(1,1,1):
                if oTermElm.GetClassName() == 'ElmLne':
                    for oLneElm in oTermElm.GetConnectedElements(1,1,1):
                        if oLneElm.GetAttribute("cpGrid") in contingencyGrids:
                            if (oLneElm.GetClassName() == 'ElmTerm') and not (oLneElm in analysed_elements) and not(oLneElm in currentTerms):
                                currentTerms.append(oLneElm)
                if oTermElm.GetClassName() == 'ElmTr2':
                    for oTrElm in oTermElm.GetConnectedElements(1,1,1):
                        if oTrElm.GetAttribute("cpGrid") in contingencyGrids:
                            if (oTrElm.GetClassName() == 'ElmTerm') and not (oTrElm in analysed_elements) and not(oTrElm in currentTerms):
                                if float(oTrElm.GetAttribute("uknom")) > 100:
                                    currentTerms.append(oTrElm)

        # Analyse faults on terminals
        ContinueSearchTerms = []
        for oTerm2 in currentTerms:
            oScOn.p_target = oTerm2
            oScOff.p_target = oTerm2
            CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm2, settings[4], settings[3], settings[5], sGenAng, iprint)
            nCalculated = nCalculated + 1
            if CCT_info[0] == 0:
                if oGenCCT == CCT_info[2]:
                    oTermName2 = getForOrLocName(oTerm2)
                    CritGetName = getForOrLocName(CCT_info[2])
                    output_list = [CCT_info[1], oTermName2, CritGetName, 0, oTermName2]
                    CCT_info_list.append(output_list)
                    analysed_elements.append(oTerm2)
                    if CCT_info[0] < CCT_treshold:
                        ContinueSearchTerms.append(oTerm2)
                lne_check2 = CheckIfTermOnMultLne(oTerm2, contingencyGrids)
            else:
                oTermName2 = getForOrLocName(oTerm2)
                CCT_Error_list.append([oTermName2, CCT_info[1]])

        # Analyse faults on lines
            if DidBranch:
                oScOff.outserv = 1
                oLneOff.outserv = 0
                for oLne2 in lne_check2[1]:
                    if not (oLne2 in analysed_elements):
                        oScOn.p_target = oLne2
                        oLneOff.p_target = oLne2
                        if oLne2.GetAttribute("bus1").GetAttribute("cterm") == oTerm2:
                            oScOn.SetAttribute("shcLocation", 10)
                        else:
                            oScOn.SetAttribute("shcLocation", 90)
                        CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne2, settings[4], settings[3], settings[5], sGenAng, iprint)
                        nCalculated = nCalculated + 1
                        if CCT_info[0] == 0:
                            if oGenCCT == CCT_info[2]:
                                oTermName2 = getForOrLocName(oTerm2)
                                CritGetName = getForOrLocName(CCT_info[2]) 
                                oLneName2 = getForOrLocName(oLne2) 
                                output_list = [CCT_info[1], oTermName2, CritGetName, 1, oLneName2]
                                CCT_info_list.append(output_list)
                                analysed_elements.append(oLne2)
                        else:
                            oLneName2 = getForOrLocName(oLne2) 
                            CCT_Error_list.append([oLneName2, CCT_info[1]])
                oScOff.outserv = 0
                oLneOff.outserv = 1
            
            else:
                NewLines = []
                for oLne3 in lne_check2[1]:
                    if not (oLne3 in analysed_elements):
                        NewLines.append(oLne3)
                if len(NewLines) > 1:
                    DidBranch = True
                    oScOff.outserv = 1
                    oLneOff.outserv = 0
                    for oLne4 in NewLines:
                        oScOn.p_target = oLne4
                        oLneOff.p_target = oLne4
                        if oLne4.GetAttribute("bus1").GetAttribute("cterm") == oTerm2:
                            oScOn.SetAttribute("shcLocation", 10)
                        else:
                            oScOn.SetAttribute("shcLocation", 90)
                        CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne4, settings[4], settings[3], settings[5], sGenAng, iprint)
                        nCalculated = nCalculated + 1
                        if CCT_info[0] == 0:
                            if oGenCCT == CCT_info[2]:
                                oTermName2 = getForOrLocName(oTerm2)
                                CritGetName = getForOrLocName(CCT_info[2]) 
                                oLneName4 = getForOrLocName(oLne4) 
                                output_list = [CCT_info[1], oTermName2, CritGetName, 1, oLneName4]
                                CCT_info_list.append(output_list)
                                analysed_elements.append(oLne4)
                        else:
                            oLneName4 = getForOrLocName(oLne4) 
                            CCT_Error_list.append([oLneName4, CCT_info[1]])
                    oScOff.outserv = 0
                    oLneOff.outserv = 1
                else:
                    for oLne5 in NewLines:
                        analysed_elements.append(oLne5)
        

    # Reset initial settings 
    oComReset.Execute() # type: ignore
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()

    # Report errors
    if CCT_Error_list:
        print("Error occurred for simulation at %s for short circuit time %f s." % (CCT_Error_list[0], CCT_Error_list[1]))
        logging.error("Error occurred for simulation at %s for short circuit time %f s." % (CCT_Error_list[0], CCT_Error_list[1]))
    return (CCT_info_list)

def GetCoupOtherSide(oCoup, oElm):
    ConnectedElements = []
    if oCoup.on_off == 1:
        for oElm2 in oCoup.GetConnectedElements(1,1,1):
            if oElm2 != oElm:
                ConnectedElements.append(oElm2)
        return(ConnectedElements)
    else:
        return(None)
    
def CheckLines(oElmLine, sLinesForSc):
    for tup in sLinesForSc:
        if oElmLine == tup[1]:
            return True
    return False

## retired because its buggy. use GetRelevantLines2
# def GetRelevantLines(sLinesForSc, sConsideredTerm, oTerm, nLines, TopRec):
#     sConsideredTerm.append(oTerm)
#     for oTermElm in oTerm.GetConnectedElements(1,1,1):
#         if oTermElm.GetClassName() == "ElmLne":
#             if not CheckLines(oTermElm, sLinesForSc):
#                 nLines = nLines + 1
#                 sLinesForSc.append((oTerm,oTermElm))
#         if oTermElm.GetClassName() == "ElmCoup":
#             sTermCoupElms = GetCoupOtherSide(oTermElm, oTerm)
#             if sTermCoupElms:
#                 for oTermCoupElm in sTermCoupElms:
#                     if oTermCoupElm.GetClassName() == "ElmTerm" and oTermCoupElm not in sConsideredTerm:
#                         sLinesForSc, sConsideredTerm, nLines = GetRelevantLines(sLinesForSc, sConsideredTerm, oTermCoupElm, nLines, False)
    
#     while nLines == 1 and TopRec:
#         NewLineElms = []
#         oExcluseTerm = sLinesForSc[0]
#         oLne = sLinesForSc[0][1]
#         for oElmLne in oLne.GetConnectedElements(1,1,1):
#             if oElmLne != oTerm and oElmLne.GetClassName() == "ElmTerm":
#                 NewLineElms.append(oElmLne)
#         for oTerm in NewLineElms:
#             sLinesForSc, sConsideredTerm, nLines = GetRelevantLines(sLinesForSc, sConsideredTerm, oTerm, nLines, True)
#         sLinesForSc.remove(oExcluseTerm)
#         nLines = nLines - 1
#     return(sLinesForSc, sConsideredTerm, nLines)

def GetRelevantLines2(sTerm):
    sConsideredLines = []
    sCurrTerms = GetAllCoupeledTerms(sTerm)
    for oTerm in sCurrTerms:
        sConnectedLines = GetLinesOfTerm(oTerm, [])
        for oConnectedLine in sConnectedLines:
            if not CheckLines(oConnectedLine, sConsideredLines):
                sConsideredLines.append((oTerm, oConnectedLine))
    
    if len(sConsideredLines) == 1:
        sConsideredLines = GetRelevantLines2Tier2(sConsideredLines)

    return(sConsideredLines)

def GetRelevantLines2Tier2(sConsideredLines):
    EntranceTerm = sConsideredLines[0][0]
    EntranceLine = sConsideredLines[0][1]
    sConsideredLines = []
    startTerm = GetLneOtherSide(EntranceTerm, EntranceLine)
    sCurrTerms = GetAllCoupeledTerms(startTerm)
    for oTerm in sCurrTerms:
        sConnectedLines = GetLinesOfTerm(oTerm, [EntranceLine])
        for oConnectedLine in sConnectedLines:
            if not CheckLines(oConnectedLine, sConsideredLines):
                sConsideredLines.append((oTerm,oConnectedLine))
    
    if len(sConsideredLines) == 1:
        sConsideredLines = GetRelevantLines2Tier2(sConsideredLines)
    
    return(sConsideredLines)

def GetAllCoupeledTerms(oTerm):
    returnTerms = []
    returnTerms += oTerm
    n_diff_Elm = 1
    while n_diff_Elm > 0:
        n_diff_Elm = 0
        for Term in returnTerms:
            currCoupTerms = GetCoupeledTerms(Term)
            only_in_currCoupTerms = [x for x in currCoupTerms if x not in returnTerms]
            n_diff_Elm += len(only_in_currCoupTerms)
            for i in only_in_currCoupTerms:
                if type(i) == pf.DataObject:
                    returnTerms.append(i)
    return(returnTerms)

def GetCoupeledTerms(oTerm):
    ReturnElms = []
    for oTermElm in oTerm.GetConnectedElements(1,1,1):
        if oTermElm.GetClassName() == "ElmTerm":
            ReturnElms.append(oTermElm)
        if oTermElm.GetClassName() == "ElmCoup":
            sCoupElm = GetCoupOtherSide(oTermElm, oTerm)
            for oCoupElm in sCoupElm:
                if oCoupElm.GetClassName() == "ElmTerm":
                    ReturnElms.append(oCoupElm)
    return list(set(ReturnElms))

def GetLneOtherSide(oTerm, oLne):
    returnElements = []
    for oElm in oLne.GetConnectedElements(1,1,1):
        if oElm.GetClassName() == "ElmTerm" and oElm != oTerm:
            returnElements.append(oElm)
    return(returnElements)

def GetLinesOfTerm(oTerm, exceptLines):
    returnLines = []
    for oElm in oTerm.GetConnectedElements(1,1,1):
        if oElm.GetClassName() == "ElmLne" and oElm not in exceptLines:
            returnLines.append(oElm)
    return (returnLines)

def setupStudyCasesTSAForLines(sGenCCT: List[pf.DataObject], ComElm_folder: pf.DataObject, studyCaseFolder: pf.DataObject, paraScriptPath: str, baseStudyCase: pf.DataObject, settings: list, iprint: bool) -> Tuple[List[pf.DataObject], List[pf.DataObject]]:
    '''
    This function creates new study cases and ComPython objects for each generator in the list sGenCCT.

    The function takes the following arguments:\n
    :param sGenCCT: a list of generators for which to create study cases.\n
    :param ComElm_folder: The folder with the angle adder and out of step detection blocks.\n
    :param studyCaseFolder: the folder in which to create the study cases.\n
    :param paraScriptPath: the path to the parallelisation script.\n
    :param baseStudyCase: the base study case from which to create copies.\n
    :param settings: Tuple of settings for dynamic simulation.\n
    :param iprint: a boolean that determines if the results should be printed.\n
    '''
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(ComElm_folder) == pf.DataObject), "The Argument 'ComElm_folder' is not of type PowerFactory.DataObject."
    assert(type(studyCaseFolder) == pf.DataObject), "The Argument 'studyCaseFolder' is not of type 'Powerfactory.DataObject"
    assert(studyCaseFolder.GetClassName() == "IntPrjfolder"), "The Argument 'studyCaseFolder' is not of class 'IntPrjfolder'."
    assert(type(paraScriptPath) == str), "The Argument 'paraScriptPath' is not of type string."
    assert(os.path.isfile(paraScriptPath)), "The Argument 'paraScriptPath' is not a valid file path."
    assert(type(baseStudyCase) == pf.DataObject), "The Argument 'baseStudyCase' is not of type 'Powerfactory.DataObject"
    assert(baseStudyCase.GetClassName() == "IntCase"), "The Argument 'baseStudyCase' is not of class 'IntCase'."
    assert(type(settings) == tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4] The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)."
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    createdStudyCases: List[pf.DataObject] = []
    createdComPython: List[pf.DataObject] = []

    # Get lines for Short circuit calculations
    sAllLinesForSc = []

    #Get bus near generator
    sSCTerms = getGenBus(sGenCCT)

    for oSCTerms in sSCTerms:
        #Get lines for calculations
        sLinesForSc= GetRelevantLines2(oSCTerms)
        sAllLinesForSc = sAllLinesForSc + sLinesForSc

    # Remove duplicates
    sAllLinesForSc = list(set(sAllLinesForSc))
    
    # Create new StudyCase for each Line in sAllLinesForSc
    for i, oLneTuple in enumerate(sAllLinesForSc):
        studyCaseName = f'SC on line {oLneTuple[1].GetAttribute("loc_name")}'

        # Create new study case from the base study case
        newStudyCase = studyCaseFolder.AddCopy(baseStudyCase)
        newStudyCase.SetAttribute("loc_name", f"{studyCaseName}")
        if newStudyCase is not None:
            if iprint:
                print(f"Created study case: {newStudyCase.GetAttribute('loc_name')}")
            createdStudyCases.append(newStudyCase)
        else:
            raise ValueError(f"Failed to create study case for {studyCaseName}.")

        # Create a new ComPython for the study case
        comPythonObject = newStudyCase.CreateObject("ComPython", "Python Skripta")
        comPythonObject.SetAttribute("filePath", paraScriptPath)

        # Define it's external objects
        DefineInputTSAForLines(comPythonObject, ComElm_folder, oLneTuple[0], oLneTuple[1], settings)
        createdComPython.append(comPythonObject)
    
    return createdStudyCases, createdComPython

def get_best_availabe_CCT_prediction(CCT_dict: dict, sGenCCT: list) -> float:
    '''
    :param CCT_dict: the dictionary of CCTs per loaction
    :param sGenCCT: the list of considered gneerators
    '''
    CCT_prediction_found = False
    CCT_Prediction = 100
    CCT_gen_out = None
    Gen_for_name_list = []
    for oGen in sGenCCT:
        oGen_for_name = oGen.GetAttribute("for_name")
        oGen_for_name = oGen_for_name.split(":")[-1]
        Gen_for_name_list.append(oGen_for_name)
    for CCT_gen in CCT_dict.keys():
        if CCT_gen in Gen_for_name_list:
            curr_prediction = CCT_dict[CCT_gen]["summary"]['cct_weighted']
            if curr_prediction < CCT_Prediction:
                CCT_gen_out = CCT_gen
                CCT_Prediction = curr_prediction
                CCT_prediction_found = True
    
    return (CCT_prediction_found, CCT_Prediction, CCT_gen_out)


def DefineInputTSAForLines(comPythonObject: pf.DataObject, ComElm_folder: pf.DataObject, oTerm: pf.DataObject, oLne: pf.DataObject, settings: list) -> bool:
    ParamTypeInputList = ["double", "double", "double", "double", "double", "double"]
    ParamNameInputList = ["tStartTSA", "tStopTSA", "tSimStepTSA", "tMaxClear", "tMinClear" ,"tStepTSA"]
    ParamValueInputList = list(map(lambda x: str(x), settings))
    comPythonObject.SetAttribute("IntType", ParamTypeInputList)
    comPythonObject.SetAttribute("IntName", ParamNameInputList)
    comPythonObject.SetAttribute("IntExpr", ParamValueInputList)
    comPythonObject.obj_name = ["oTermInput","oLneInput","ComElm_folder"] # type: ignore
    comPythonObject.obj_id = [oTerm, oLne, ComElm_folder] # type: ignore
    # comPythonObject.obj_desc = [""] # type: ignore
    return (True)

def parse_number(value):
    if value == "":
        value = "0"
    value = value.strip().replace(",", ".")
    try:
        return int(value) if "." not in value else float(value)
    except ValueError:
        return value

# main functions

def TSAForTermAtGen(app, settings, grid, sGenCCT, sGenRecord, iprint):
    '''
    This function runs the Transient stability assessment for contingencies (3 phase short circuits) on terminals at generators.
    The Arguments to the function are:\n

    app - the powerfactory application in which the desired project should already be activated.\n
    setting - the desired settings tuple which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [5] The critical clearing time accuracy (in s)\n
    grid - the grid object in which you wish to create the Out Of Step detection logic\n
    sGenCCT - the generators near which contingencies for TSA should be considered. \n
    sGenRecord - Generators near which contingencies should be considered. \n
    iprint - A boolean that determines if the results should be printed\n

    The function returns a list of lists. The number of inner lists is equal to the number of events to be evaluated. Each inner list consists of:\n
        -[0] The critical clearing time (in s)\n
        -[1] The generator which was critical for an event where the clearing time was longer than the critical clearing time\n
        -[2] The element on which the critical clearing time was evaluated on.
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(grid) == pf.DataObject), "The Argument 'grid' is not of type 'Powerfactory.DataObject"
    assert(grid.GetClassName() == "ElmNet"), "The Argument 'grid' is not of class 'ElmNet'."
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sGenRecord) == list), "The Argument 'sGenRecord' is not of type list"
    for i in range(len(sGenRecord)):
        assert(sGenRecord[i].GetClassName() == "ElmSym"), "The Argument 'sGenRecord["+str(i)+"] is not of class 'ElmSym'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    OOSDetName = "OOSDetection"

    # Get terminals at generators
    ScTerms = getGenBus(sGenCCT)
    
    # Get dynamic models folder
    dyn_folder = app.GetProjectFolder("blk")
    AngAdd_fold = dyn_folder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = grid.CreateObject("IntFolder", "AngleAdderElmss")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder)

    # Create Out Of Step detection blocks or enable them, if they are already created
    OOSDetFrm = OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)

    # Run CCT evaluation
    CCT_info_list = []
    CCT_Error_list = []
    for oGen, sTermList in tqdm.tqdm(zip(sGenCCT, ScTerms)):
        for oTerm in sTermList:
            logging.info("----------------------------------------------------------------------------------------------")
            logging.info("calculating contingencies at")
            oScOn.p_target = oTerm
            oScOff.p_target = oTerm
            CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm, settings[4], settings[3], settings[2], sGenAng, iprint)
            ScTermName = getForOrLocName(oTerm)
            CritGetName = getForOrLocName(CCT_info[2])
            output_list = [CCT_info[1], ScTermName, CritGetName, 0, ScTermName]
            if CCT_info[0] == 0:
                if oGen == CCT_info[2]:
                    CCT_info_list.append(output_list)
            else:
                ScTermName = getForOrLocName(oTerm)
                CCT_Error_list.append([oTerm, CCT_info[1]])
    # Reset initial settings
    oComReset.Execute()
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()
    AngAdd_fold.Delete()
    ComElm_folder.Delete()

    # report errors
    for entry in CCT_Error_list:
        print("Error occured for simulation at %s for short circuit time %f s." % (entry[0], entry[1]))
        logging.error("Error occured for simulation at %s for short circuit time %f s." % (entry[0], entry[1]))

    return (CCT_info_list)

def TSAForTermAtGenAndLnes(app, settings, grid, contingencyGrids, sGenCCT, sGenRecord, iprint):
    '''
    This function runs the Transient stability assessment for contingencies (3 phase short circuits) on terminals at generators and if the terminal
    is connected to multiple lines, for contingencies (3 phase short circuits) on those lines.
    The Arguments to the function are:\n

    app - the powerfactory application in which the desired project should already be activated.\n
    setting - the desired settings tuple which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [5] The critical clearing time accuracy (in s)\n
    grid - the grid object in which you wish to create the Out Of Step detection logic\n
    contingencyGrids -  a list of grids in which contingencies should be considered.\n
    iprint - A boolean that determines if the results should be printed\n

    The function returns a list of lists. The number of inner lists is equal to the number of events to be evaluated. Each inner list consists of:\n
        -[0] The critical clearing time (in s)\n
        -[1] The terminal at which or near which the fault was conducted at\n
        -[2] The generator which was critical for an event where the clearing time was longer than the critical clearing time\n
        -[3] The type of fault (0 - fault on treminal, 1 - fault on line)\n
        -[4]The element on which the critical clearing time was evaluated on.
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4]4The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(grid) == pf.DataObject), "The Argument 'grid' is not of type 'Powerfactory.DataObject"
    assert(grid.GetClassName() == "ElmNet"), "The Argument 'grid' is not of class 'ElmNet'."
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sGenRecord) == list), "The Argument 'sGenRecord' is not of type list"
    for i in range(len(sGenRecord)):
        assert(sGenRecord[i].GetClassName() == "ElmSym"), "The Argument 'sGenRecord["+str(i)+"] is not of class 'ElmSym'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    OOSDetName = "OOSDetection"

    # Terminals at generators
    ScTerms = getGenBus(sGenCCT)

    # Get dynamic models folder
    dyn_folder = app.GetProjectFolder("blk")   
    AngAdd_fold = dyn_folder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = grid.CreateObject("IntFolder", "AngleAdderElms")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder)

    # Create Out Of Step detection blocks or enable them, if they are already created
    OOSDetFrm = OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)

    # Run CCT evaluation
    CCT_info_list = []
    CCT_Error_list = []
    for oGen, sTermList in tqdm.tqdm(zip(sGenCCT, ScTerms)):
        for oTerm in sTermList:
            # run CCT on generator terminal
            oScOn.p_target = oTerm
            oScOff.p_target = oTerm
            CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm, settings[4], settings[3], settings[2], sGenAng, iprint)
            ScTermName = getForOrLocName(oTerm)
            CritGetName = getForOrLocName(CCT_info[2])
            output_list = [CCT_info[1], ScTermName, CritGetName, 0, ScTermName]
            if CCT_info[0] == 0:
                if CCT_info[2] == oGen:
                    CCT_info_list.append(output_list)
            else:
                ScTermName = getForOrLocName(oTerm)
                CCT_Error_list.append([ScTermName, CCT_info[1]])

            # run CCT on connected lines if necessary
            lne_check = CheckIfTermOnMultLne(oTerm, contingencyGrids)
            if lne_check[0]:
                oScOff.outserv = 1
                oLneOff.outserv = 0
                for oLne in lne_check[1]:
                    oScOn.p_target = oLne
                    oLneOff.p_target = oLne
                    if oLne.GetAttribute("bus1").GetAttribute("cterm") == oTerm:
                        oScOn.SetAttribute("shcLocation", 10)
                    else:
                        oScOn.SetAttribute("shcLocation", 90)
                    CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne, settings[4], settings[3], settings[2], sGenAng, iprint)
                    if CCT_info[0] == 0:
                        if oGen == CCT_info[2]:
                            ScTermName = getForOrLocName(oTerm)
                            CritGetName = getForOrLocName(CCT_info[2])
                            oLneName = getForOrLocName(oLne)
                            output_list = [CCT_info[1], ScTermName, CritGetName, 1, oLneName]
                            CCT_info_list.append(output_list)
                    else:
                        oLneName = getForOrLocName(oLne)
                        CCT_Error_list.append([oLneName, CCT_info[1]])
                oScOff.outserv = 0
                oLneOff.outserv = 1

    # Reset initial settings
    oComReset.Execute()
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()
    AngAdd_fold.Delete()
    ComElm_folder.Delete()

    
    for entry in CCT_Error_list:
        print("Error occured for simulation at %s for short circuit time %f s." % (entry[0], entry[1]))

    return (CCT_info_list)

def TSAUntilTreshold(app, settings, grid, contingencyGrids, sGenCCT, sGenRecord, iprint):
    '''
    This function runs the Transient stability assessment for contingencies (3 phase short circuits) on elements starting terminals at generators. If the CCT of the current element is lower
    than the given treshold, the function calculates the CCT on all adjacent terminals and lines, until the treshold is met, or the critical machine differs from the starting machine.
    The Arguments to the function are:\n

    app - the powerfactory application in which the desired project should already be activated.\n
    setting - the desired settings tuple which should consist of (in that order):\n
        - [0] The simulation start time (in s)\n
        - [1] The simulation stop time (in s)\n
        - [2] The simulation step time (in s)\n
        - [3] The maximum fault clearing time (in s)\n
        - [4] The minimum fault clearing time (in s)\n
        - [6] The Threshold at which to stop searching for CCTs (in s)\n\
    grid - the grid object in which you wish to create the Out Of Step detection logic\n
    contingencyGrids - a list of grids in which contingencies should be considered.\n
    sGenCCT - the generators near which contingencies for TSA should be considered. \n
    sGenRecord - Generators near which contingencies should be considered. \n
    iprint - A boolean that determines if the results should be printed\n

    The function returns a list of lists. The number of inner lists is equal to the number of events to be evaluated. Each inner list consists of:\n
        -[0] The critical clearing time (in s)\n
        -[1] The terminal at which or near which the fault was conducted at\n
        -[2] The generator which was critical for an event where the clearing time was longer than the critical clearing time\n
        -[3] The type of fault (0 - fault on treminal, 1 - fault on line)\n
        -[4]The element on which the critical clearing time was evaluated on.
    '''

    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == tuple), "Given Argument 'settings' is not a tuple."
    assert(len(settings) == 7), "Given Argument 'settings' does not have 7 entrys as it should. The needed entrys are:\n\
                                - [0] The simulation start time (in s)\n\
                                - [1] The simulation stop time (in s)\n\
                                - [2] The simulation step time (in s)\n\
                                - [3] The maximum fault clearing time (in s)\n\
                                - [4] The minimum fault clearing time (in s)\n\
                                - [5] The critical clearing time accuracy (in s)\n\
                                - [6] The maximum critical clearing time"
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(grid) == pf.DataObject), "The Argument 'grid' is not of type 'Powerfactory.DataObject"
    assert(grid.GetClassName() == "ElmNet"), "The Argument 'grid' is not of class 'ElmNet'."
    assert(type(contingencyGrids) == list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) == pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    for i in range(len(sGenCCT)):
        assert(sGenCCT[i].GetClassName() == "ElmSym"), "The Argument 'sGenCCT["+str(i)+"] is not of class 'ElmSym'"
    assert(type(sGenRecord) == list), "The Argument 'sGenRecord' is not of type list"
    for i in range(len(sGenRecord)):
        assert(sGenRecord[i].GetClassName() == "ElmSym"), "The Argument 'sGenRecord["+str(i)+"] is not of class 'ElmSym'"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")
    oComReset = app.GetFromStudyCase("ComReset")

    OOSDetName = "OOSDetection"

    # Terminals at generators
    ScTerms = getGenBus(sGenCCT)

    # Get dynamic models folder
    dyn_folder = app.GetProjectFolder("blk")
    AngAdd_fold = dyn_folder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = grid.CreateObject("IntFolder", "AngleAdderElms")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder)

    # Create Out Of Step detection blocks or enable them, if they are already created
    OOSDetFrm = OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # Setup desired parameters and create events for TSA
    InitialParams = setUserParams(oComInc, oComSim, settings[0], settings[1], settings[2])
    oScOn, oScOff, oLneOff, sEvents = setupSimEvents(oComInc)
 
    CCT_treshold = settings[6]
    # Run CCT Evaluation
    CCT_info_list = []
    CCT_Error_list = []
    for oGen, sTermList in tqdm.tqdm(zip(sGenCCT, ScTerms)):
        analysed_elements = []
        ContinueSearchTerms = []

        for oTerm in sTermList:
            DidBranch = False
            # Analyse fault on terminal closest to generator
            oScOn.p_target = oTerm
            oScOff.p_target = oTerm
            CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm, settings[4], settings[3], settings[2], sGenAng, iprint)
            if CCT_info[0] == 0:
                if oGen == CCT_info[2]:
                    ScTermName = getForOrLocName(oTerm)
                    CritGetName = getForOrLocName(CCT_info[2])
                    output_list = [CCT_info[1], ScTermName, CritGetName, 0, ScTermName]
                    CCT_info_list.append(output_list)
                    analysed_elements.append(oTerm)
                    if CCT_info[0] < CCT_treshold:
                        ContinueSearchTerms.append(oTerm)
                lne_check = CheckIfTermOnMultLne(oTerm, contingencyGrids)
            else:
                ScTermName = getForOrLocName(oTerm)
                CCT_Error_list.append([ScTermName, CCT_info[1]])

            # If there is multiple lines analyse faults on those line 
            if lne_check[0]:
                DidBranch = True
                oScOff.outserv = 1
                oLneOff.outserv = 0
                for oLne in lne_check[1]:
                    oScOn.p_target = oLne
                    oLneOff.p_target = oLne
                    if oLne.GetAttribute("bus1").GetAttribute("cterm") == oTerm:
                        oScOn.SetAttribute("shcLocation", 10)
                    else:
                        oScOn.SetAttribute("shcLocation", 90)
                    CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne, settings[4], settings[3], settings[2], sGenAng, iprint)
                    if CCT_info[0] == 0:
                        if oGen == CCT_info[2]:
                            ScTermName = getForOrLocName(oTerm)
                            CritGetName = getForOrLocName(CCT_info[2])
                            oLneName = getForOrLocName(oLne)
                            output_list = [CCT_info[1], ScTermName, CritGetName, 1, oLneName]
                            CCT_info_list.append(output_list)
                            analysed_elements.append(oLne)
                    else:
                        oLneName = getForOrLocName(oLne)
                        CCT_Error_list.append([oLneName, CCT_info[1]])
                oScOff.outserv = 0
                oLneOff.outserv = 1
            else:
                for oLne in lne_check[1]:
                    analysed_elements.append(oLne)

            # while the terminal short circuit is smaller than the threshold
            while ContinueSearchTerms:
                currentTerms = []

                oComReset.Execute()
                # Get Terminals to analyse
                for oTerm1 in ContinueSearchTerms:
                    for oTermElm in oTerm1.GetConnectedElements(1,1,1):
                        if oTermElm.GetClassName() == 'ElmLne':
                            for oLneElm in oTermElm.GetConnectedElements(1,1,1):
                                if oLneElm.GetAttribute("cpGrid") in contingencyGrids:
                                    if (oLneElm.GetClassName() == 'ElmTerm') and not (oLneElm in analysed_elements) and not(oLneElm in currentTerms):
                                        currentTerms.append(oLneElm)
                        if oTermElm.GetClassName() == 'ElmTr2':
                            for oTrElm in oTermElm.GetConnectedElements(1,1,1):
                                if oTrElm.GetAttribute("cpGrid") in contingencyGrids:
                                    if (oTrElm.GetClassName() == 'ElmTerm') and not (oTrElm in analysed_elements) and not(oTrElm in currentTerms):
                                        if float(oTrElm.GetAttribute("uknom")) > 100:
                                            currentTerms.append(oTrElm)
                
                # Analyse faults on terminals
                ContinueSearchTerms = []
                for oTerm2 in currentTerms:
                    oScOn.p_target = oTerm2
                    oScOff.p_target = oTerm2
                    CCT_info = TermCCT(app, oComInc, oComSim, oScOn, oScOff, OOSDetFrm, oTerm2, settings[4], settings[3], settings[2], sGenAng, iprint)
                    if CCT_info[0] == 0:
                        if oGen == CCT_info[2]:
                            ScTermName2 = getForOrLocName(oTerm2)
                            CritGetName = getForOrLocName(CCT_info[2])
                            output_list = [CCT_info[1], ScTermName2, CritGetName, 0, ScTermName2]
                            CCT_info_list.append(output_list)
                            analysed_elements.append(oTerm2)
                            if CCT_info[0] < CCT_treshold:
                                ContinueSearchTerms.append(oTerm2)
                        lne_check2 = CheckIfTermOnMultLne(oTerm2, contingencyGrids)
                    else:
                        ScTermName2 = getForOrLocName(oTerm2)
                        CCT_Error_list.append([ScTermName2, CCT_info[1]])

                # Analyse faults on lines
                    if DidBranch:
                        oScOff.outserv = 1
                        oLneOff.outserv = 0
                        for oLne2 in lne_check2[1]:
                            if not (oLne2 in analysed_elements):
                                oScOn.p_target = oLne2
                                oLneOff.p_target = oLne2
                                if oLne2.GetAttribute("bus1").GetAttribute("cterm") == oTerm2:
                                    oScOn.SetAttribute("shcLocation", 10)
                                else:
                                    oScOn.SetAttribute("shcLocation", 90)
                                CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne2, settings[4], settings[3], settings[2], sGenAng, iprint)
                                if CCT_info[0] == 0:
                                    if oGen == CCT_info[2]:
                                        ScTermName2 = getForOrLocName(oTerm2)
                                        CritGetName = getForOrLocName(CCT_info[2]) 
                                        oLneName2 = getForOrLocName(oLne2) 
                                        output_list = [CCT_info[1], ScTermName2, CritGetName, 1, oLneName2]
                                        CCT_info_list.append(output_list)
                                        analysed_elements.append(oLne2)
                                else:
                                    oLneName2 = getForOrLocName(oLne2)
                                    CCT_Error_list.append([oLneName2, CCT_info[1]])
                        oScOff.outserv = 0
                        oLneOff.outserv = 1
                    
                    else:
                        NewLines = []
                        for oLne3 in lne_check2[1]:
                            if not (oLne3 in analysed_elements):
                                NewLines.append(oLne3)
                        if len(NewLines) > 1:
                            DidBranch = True
                            oScOff.outserv = 1
                            oLneOff.outserv = 0
                            for oLne4 in NewLines:
                                oScOn.p_target = oLne4
                                oLneOff.p_target = oLne4
                                if oLne4.GetAttribute("bus1").GetAttribute("cterm") == oTerm2:
                                    oScOn.SetAttribute("shcLocation", 10)
                                else:
                                    oScOn.SetAttribute("shcLocation", 90)
                                CCT_info = LneCCT(app, oComInc, oComSim, oScOn, oLneOff, OOSDetFrm, oLne4, settings[4], settings[3], settings[2], sGenAng, iprint)
                                if CCT_info[0] == 0:
                                    if oGen == CCT_info[2]:
                                        ScTermName2 = getForOrLocName(oTerm2)
                                        CritGetName = getForOrLocName(CCT_info[2]) 
                                        oLneName4 = getForOrLocName(oLne4) 
                                        output_list = [CCT_info[1], ScTermName2, CritGetName, 1, oLneName4]
                                        CCT_info_list.append(output_list)
                                        analysed_elements.append(oLne4)
                                else:
                                    oLneName4 = getForOrLocName(oLne4)
                                    CCT_Error_list.append([oLneName4, CCT_info[1]])
                            oScOff.outserv = 0
                            oLneOff.outserv = 1
                        else:
                            for oLne5 in NewLines:
                                analysed_elements.append(oLne5)

    # Reset initial settings
    oComReset.Execute()
    setInitialParams(oComInc, oComSim, InitialParams)
    setInitialEvents(oComReset, oScOn, oScOff, oLneOff, sEvents)
    oScOn.Delete()
    oScOff.Delete()
    oLneOff.Delete()
    AngAdd_fold.Delete()
    ComElm_folder.Delete()
    
    # report errors
    for entry in CCT_Error_list:
        print("Error occured for simulation at %s for short circuit time %f s." % (entry[0], entry[1]))
        logging.error("Error occured for simulation at %s for short circuit time %f s." % (entry[0], entry[1]))
    
    return(CCT_info_list)

def TSAForTermAtGenParallel(app: pf.Application, settings: tuple, grid: pf.DataObject, sGenCCT: List[pf.DataObject], sGenRecord: List[pf.DataObject], iprint: bool):
    '''
    Run transient stability analysis for a set of generators in parallel.

    This function sets up and executes parallel TSA simulations by creating 
    separate study cases and ComPython scripts for each generator contingency. 
    It then uses a ComTask object to manage the parallel execution within PowerFactory.

    Note: Parallel execution might not improve performance for already fast 
    sequential runs (e.g., < 150s). Consider using 'TSAForTermAtGen' in such cases.

    :param app: The PowerFactory application object with the desired project activated.
    :param settings: Tupleof settings for dynamic simulation.
    :param grid: The grid in which to store OutOfStep blocks.
    :param sGenCCT: List of generator objects ('ElmSym') near which contingencies 
                    (3-phase short circuits on terminals) should be simulated.
    :param sGenRecord: List of generator objects ('ElmSym') which are monitored
                       for OutOfStep Detection.
    :param iprint: Flag to control printing of progress messages during setup.
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == tuple), "Given Argument 'settings' is not of type tuple"    
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(grid) == pf.DataObject), "Given Argument 'grid' is not of type powerfactory.DataObject"
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    assert(type(sGenRecord) == list), "The Argument 'sGenRecord' is not of type list"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    PFSupport.Utils.clearOutputWindow(app)
    activeProject: pf.DataObject = app.GetActiveProject()
    
    # get active study case name
    ActStudCaseName = os.getenv("stud_case")

    # create OOS detection frame
    OOSDetName = "OOSDetection"
    
    # Get dynamic models folder
    dyn_folder = app.GetProjectFolder("blk")
    AngAdd_fold = dyn_folder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = grid.CreateObject("IntFolder", "AngleAdderElms")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder)
        
    # Create Out Of Step detection blocks or enable them, if they are already created
    OOSDetFrm = OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # Obtain Study Cases folder from the project
    studyCaseFolder: pf.DataObject = activeProject.GetContents("Study Cases.IntPrjfolder", 1)[0]
    if studyCaseFolder is None:
        print("Failed to retrieve the Study Case folder.")
        logging.warning("Failed to retrieve the Study Case folder.")
        raise ValueError("Study Case folder not found.")
    
    # Obtain the base StudyCase that we will create copies of
    baseStudyCase: pf.DataObject = studyCaseFolder.GetContents(ActStudCaseName, 1)[0]
    if baseStudyCase is None:
        print("Failed to retrieve the base Study Case.")
        logging.warning("Failed to retrieve the base Study Case.")
        raise ValueError("Base Study Case not found.")
    
    # Setup parallelisation script path
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    basePath = os.path.dirname(scriptDir) # Go one level up from the script's directory
    targetScriptRelativePath = os.path.join('parallelisation', "TSAForTermAtSingleGen.py")
    targetScriptPath = os.path.join(basePath, targetScriptRelativePath)

    # set parallelisation script package path
    SetCurrVenvInScript(targetScriptPath, iprint)

    # Setup temporary results directory (needs te be set the same path as in parallelisation script TSAForTermAtSingleGen.py)
    tempResultsDir = os.path.join(basePath, "parallelisation\\temp_results")

    # Create StudyCases for parallelisation
    createdStudyCases, createdComPython = setupStudyCases(sGenCCT, ComElm_folder, studyCaseFolder, targetScriptPath, baseStudyCase, settings, iprint)
    # Create ComTask in Study Cases folder (Task Automation)
    comTask = studyCaseFolder.CreateObject("ComTasks", "Avtomatizacija")

    # Append StudyCase and ComPython scripts for each StudyCase to the ComTask
    for id, studyCase in enumerate(createdStudyCases):
        comTask.AppendStudyCase(studyCase) # type: ignore
        comTask.AppendCommand(createdComPython[id], 0) # type: ignore

    oSetUser = app.GetFromStudyCase("*.SetUser")
    # Execute the ComTask command
    if iprint:
        print("Executing ComTask command. Transferring data to parallel processes and starting execution...")
        logging.info("Executing ComTask command. Transferring data to parallel processes and starting execution...")
    parallel_time_start = time.time()
    comTask.Execute() # type: ignore
    parallel_time_end = time.time()
    if iprint:
        print("ComTask command finished.")
        logging.info("ComTask commad finished.")
    # Get output from the OutputWindow (to check if everything went well)
    outputContent = PFSupport.Utils.getOutputWindowContent(app)
    if isinstance(outputContent, list):
        for line in outputContent:
            logging.info(f"PF OutputWindow: {line}")
    else:
        logging.info(f"PF OutputWindow: {outputContent}") # Log as is if not a list

    # Read all the results from the temporary files created by the ComPython scripts
    CCT_info_lists = ReadResFilesTSA(sGenCCT, tempResultsDir)
    
    # Convert DataObject string references back to DataObject instances (example: 'Bus 02.ElmTerm' --> Bus 02 as pf.DataObject)
    # CCT_info_lists_refined = RedefineToOriginalElementsTSATreshold(app, CCT_info_lists)
    
    # merge all the lists back into one
    final_output = []
    for i in CCT_info_lists:
        final_output = final_output + i

    # Convert DataObject string references back to DataObject instances (example: 'Bus 02.ElmTerm' --> Bus 02 as pf.DataObject)
    # CCT_info_lists_refined = RedefineToOriginalElements(app, CCT_info_lists)
    # Clean up temporary files
    CleanupTemp(tempResultsDir)

    # Clean up created study cases
    for studyCase in createdStudyCases:
        studyCase.Delete()

    ComElm_folder.Delete()

    # return CCT_info_lists_refined
    return final_output

def TSAUntilTresholdParallel(app: pf.Application, settings: list, dynModGrid: pf.DataObject, contingencyGrids: list[pf.DataObject], sGenCCT: List[pf.DataObject], sGenRecord: List[pf.DataObject], iprint: bool):
    '''
    Run transient stability analysis for a set of generators in parallel.

    This function sets up and executes parallel TSA simulations by creating 
    separate study cases and ComPython scripts for each generator contingency. 
    It then uses a ComTask object to manage the parallel execution within PowerFactory.

    Note: Parallel execution might not improve performance for already fast 
    sequential runs (e.g., < 150s). Consider using 'TSAForTermAtGen' in such cases.

    :param app: The PowerFactory application object with the desired project activated.
    :param settings: List of settings for dynamic simulation.
    :param CCT_treshold: setting for when to stop searching for new elements to calculate CCTs.
    :param nRecord: The number of cases above which to stop analysing.
    :param dynModGrid: The grid in which to store OutOfStep blocks.
    :param contingencyGrids: a list of grids in which contingencies should be considered.
    :param sGenCCT: List of generator objects ('ElmSym') near which contingencies 
                    (3-phase short circuits on terminals) should be simulated.
    :param sGenRecord: List of generator objects ('ElmSym') which are monitored
                       for OutOfStep Detection.
    :param iprint: Flag to control printing of progress messages during setup.
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == tuple), "Given Argument 'settings' is not of type tuple."
    assert(len(settings) == 8), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                            - [0] The simulation start time (in s)\n\
                            - [1] The simulation stop time (in s)\n\
                            - [2] The simulation step time (in s)\n\
                            - [3] The maximum fault clearing time (in s)\n\
                            - [4] The minimum fault clearing time (in s)\n\
                            - [5] The critical clearing time accuracy (in s)\n\
                            - [6] The Threshold at which to stop searching for CCTs (in s)\n\
                            - [7] The number at which to stop coninue searching for further elements in grid."
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(type(settings[6]) in [int, float]), "The critical clearing trehold (settings[6]) is not a number (int or float)"
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[6]), "The minimum fault clearing time (settings[4]), should be lower than the critical clearing trshold (settings[6])."
    assert(settings[6] < settings[3]), "The critical clearing treshold (settings[6]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(dynModGrid) == pf.DataObject), "Given Argument 'dynModGrid' is not of type powerfactory.DataObject"
    assert(type(contingencyGrids) == list), "Argument 'contigencyGrids' is not of type list"
    for i, val in enumerate(contingencyGrids):
        assert(type(val) == pf.DataObject), "Argument 'contingencyGrids["+str(i)+"]' is not of type powerfactory.DataObject"
        assert(val.GetClassName() == "ElmNet"), "Argument 'contingencyGrids["+str(i)+"]' is not of class 'ElmNet'"
    assert(type(settings[6]) in [float, int]), "Given Argument 'settings[6]' is not of type float or int"
    assert(type(settings[7]) == int), "Givne Argumen 'settings[7]' is not of type int."
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    assert(type(sGenRecord) == list), "The Argument 'sGenRecord' is not of type list"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    PFSupport.Utils.clearOutputWindow(app)
    activeProject: pf.DataObject = app.GetActiveProject()

    # get active study case name
    ActStudCaseName = os.getenv("stud_case")

    # create OOS detection frame
    OOSDetName = "OOSDetection"
    
    # Get dynamic models folder
    dyn_folder = app.GetProjectFolder("blk")
    AngAdd_fold = dyn_folder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = dynModGrid.CreateObject("IntFolder", "AngleAdderElms")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder)
        
    # Create Out Of Step detection blocks or enable them, if they are already created
    OOSDetFrm = OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # Obtain Study Cases folder from the project
    studyCaseFolder: pf.DataObject = activeProject.GetContents("Study Cases.IntPrjfolder", 1)[0]
    if studyCaseFolder is None:
        print("Failed to retrieve the Study Case folder.")
        raise ValueError("Study Case folder not found.")
    
    # Obtain the base StudyCase that we will create copies of
    baseStudyCase: pf.DataObject = studyCaseFolder.GetContents(ActStudCaseName, 1)[0]
    if baseStudyCase is None:
        print("Failed to retrieve the base Study Case.")
        raise ValueError("Base Study Case not found.")
    
    # Setup parallelisation script path
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    basePath = os.path.dirname(scriptDir) # Go one level up from the script's directory
    targetScriptRelativePath = os.path.join('parallelisation', "TSAUntilTreshold.py")
    targetScriptPath = os.path.join(basePath, targetScriptRelativePath)

    # set parallelisation script package path
    SetCurrVenvInScript(targetScriptPath, iprint)

    # Setup temporary results directory (needs te be set the same path as in parallelisation script SAUntilTreshold.py)
    tempResultsDir = os.path.join(basePath, "parallelisation\\temp_results")

    # Create StudyCases for parallelisation
    createdStudyCases, createdComPython = setupStudyCasesTSAUntilTreshold(sGenCCT, ComElm_folder, studyCaseFolder, targetScriptPath, baseStudyCase, settings, contingencyGrids, iprint)
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
        logging.info(f"PF OutputWindow: {outputContent}") # Log as is if not a list

    # Read all the results from the temporary files created by the ComPython scripts
    CCT_info_lists = ReadResFilesTSA(sGenCCT, tempResultsDir)
    
    # Convert DataObject string references back to DataObject instances (example: 'Bus 02.ElmTerm' --> Bus 02 as pf.DataObject)
    # CCT_info_lists_refined = RedefineToOriginalElementsTSATreshold(app, CCT_info_lists)
    
    # merge all the lists back into one
    final_output = []
    for i in CCT_info_lists:
        final_output = final_output + i

    # Clean up temporary files
    CleanupTemp(tempResultsDir)

    # Clean up created study cases
    for studyCase in createdStudyCases:
        studyCase.Delete()

    ComElm_folder.Delete()
    
    return final_output

def TSAForLinesParallel(app: pf.Application, settings: list, dynModGrid: pf.DataObject, sGenCCT: List[pf.DataObject], sGenRecord: List[pf.DataObject], iprint: bool):
    '''
    Run transient stability analysis for a set of generators in parallel.

    This function sets up and executes parallel TSA simulations by creating 
    separate study cases and ComPython scripts for each generator contingency. 
    It then uses a ComTask object to manage the parallel execution within PowerFactory.

    Note: Parallel execution might not improve performance for already fast 
    sequential runs (e.g., < 150s). Consider using 'TSAForTermAtGen' in such cases.

    :param app: The PowerFactory application object with the desired project activated.
    :param settings: List of settings for dynamic simulation.
    :param dynModGrid: The grid in which to store OutOfStep blocks.
    :param sGenCCT: List of generator objects ('ElmSym') near which contingencies 
                    (3-phase short circuits on lines) should be simulated.
    :param sGenRecord: List of generator objects ('ElmSym') which are monitored
                       for OutOfStep Detection.
    :param iprint: Flag to control printing of progress messages during setup.
    '''
    assert(type(app) == pf.Application), "Given Argument 'app' is not a powerfactory application."
    assert(type(settings) == tuple), "Given Argument 'settings' is not of type tuple."
    assert(len(settings) == 6), "Given Argument 'settings' does not have 6 entrys as it should. The needed entrys are:\n\
                            - [0] The simulation start time (in s)\n\
                            - [1] The simulation stop time (in s)\n\
                            - [2] The simulation step time (in s)\n\
                            - [3] The maximum fault clearing time (in s)\n\
                            - [4] The minimum fault clearing time (in s)\n\
                            - [5] The critical clearing time accuracy (in s)\n\
                                "
    for i in range(len(settings)):
        assert(type(settings[i]) in [int, float]), "The settings entry in possition "+str(i)+" is not of type int or float."
    assert(settings[0] <= 0), "The simulation start time (settings[0]), should be higher or equal to 0 s."
    assert(settings[0] < settings[4]), "The simulation start time (settings[0]), should be lower than minimum fault clearing time (settings[4])."
    assert(settings[4] < settings[3]), "The minimum fault clearing time (settings[4]), should be lower than the maximum fault clearing time (settings[3])."
    assert(settings[3] < settings[1]), "The maximum fualt clearing time (settings[3]), should be lower than the simulation stop time (settings[1])."
    assert(type(dynModGrid) == pf.DataObject), "Given Argument 'dynModGrid' is not of type powerfactory.DataObject."
    assert(type(sGenCCT) == list), "The Argument 'sGenCCT' is not of type list"
    assert(type(sGenRecord) == list), "The Argument 'sGenRecord' is not of type list"
    assert(type(iprint) == bool), "The Argument 'iprint' is not of type boolean."

    PFSupport.Utils.clearOutputWindow(app)
    activeProject: pf.DataObject = app.GetActiveProject()

    # get active study case name
    ActStudCaseName = os.getenv("stud_case")

    # create OOS detection frame
    OOSDetName = "OOSDetection"
    
    # Get dynamic models folder
    dyn_folder = app.GetProjectFolder("blk")
    AngAdd_fold = dyn_folder.CreateObject("IntFolder", "AngleAdderDynTyps")

    # Create the ComElm folder
    ComElm_folder = dynModGrid.CreateObject("IntFolder", "AngleAdderElms")

    # Create list of frames that calculate absolute angles and list used for detectiong of critical generator
    sGenAng, sAng = CreateOutOfStepFrame(app, sGenRecord, AngAdd_fold, ComElm_folder)
        
    # Create Out Of Step detection blocks or enable them, if they are already created
    OOSDetFrm = OutOfStep.CreateOOSDet(OOSDetName, AngAdd_fold, ComElm_folder, sAng)
    OutOfStep.EnableComElm(OOSDetName, ComElm_folder)

    # Obtain Study Cases folder from the project
    studyCaseFolder: pf.DataObject = activeProject.GetContents("Study Cases.IntPrjfolder", 1)[0]
    if studyCaseFolder is None:
        print("Failed to retrieve the Study Case folder.")
        raise ValueError("Study Case folder not found.")
    
    # Obtain the base StudyCase that we will create copies of
    baseStudyCase: pf.DataObject = studyCaseFolder.GetContents(ActStudCaseName, 1)[0]
    if baseStudyCase is None:
        print("Failed to retrieve the base Study Case.")
        raise ValueError("Base Study Case not found.")
    
    # Setup parallelisation script path
    scriptDir = os.path.dirname(os.path.abspath(__file__))
    basePath = os.path.dirname(scriptDir) # Go one level up from the script's directory
    targetScriptRelativePath = os.path.join('parallelisation', "TSAForLines.py")
    targetScriptPath = os.path.join(basePath, targetScriptRelativePath)

    # set parallelisation script package path
    SetCurrVenvInScript(targetScriptPath, iprint)

    # Setup temporary results directory (needs te be set the same path as in parallelisation script TSAForLines.py)
    tempResultsDir = os.path.join(basePath, "parallelisation\\temp_results")

    # Create StudyCases for parallelisation
    createdStudyCases, createdComPython = setupStudyCasesTSAForLines(sGenCCT, ComElm_folder, studyCaseFolder, targetScriptPath, baseStudyCase, settings, iprint)
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
        logging.info(f"PF OutputWindow: {outputContent}") # Log as is if not a list

    # Read all the results from the temporary files created by the ComPython scripts
    # Get lines for Short circuit calculations
    sOnlyLinesForSc = []

    #Get bus near generator
    sSCTerms = getGenBus(sGenCCT)

    for oSCTerms in sSCTerms:
        #Get lines for calculations
        sLinesForSc = GetRelevantLines2(oSCTerms)
        for LineTup in sLinesForSc:
            sOnlyLinesForSc.append(LineTup[1])

    # Remove duplicates
    sOnlyLinesForSc = list(set(sOnlyLinesForSc))

    CCT_info_lists = ReadResFilesTSA(sOnlyLinesForSc, tempResultsDir)

    # Clean up temporary files
    CleanupTemp(tempResultsDir)

    # Clean up created study cases
    for studyCase in createdStudyCases:
        studyCase.Delete()

    ComElm_folder.Delete()
    
    return CCT_info_lists