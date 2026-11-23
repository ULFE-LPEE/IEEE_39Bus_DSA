'''
Author: Matjaz Skrlec
date: 23. 03. 2026
version: 1.0
description: This is the module used for free run osicllation detection
'''

#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getenv("PowerfactoryPyFilePath"))
import powerfactory as pf
from PFSupport.CreateObjects import CreateBlkDef
from collections.abc import Iterable
from numbers import Number
import logging
# -------------------------------------------------------------------------------------------------
## classes
# -------------------------------------------------------------------------------------------------
## functions

## support functions ------------------
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

def CreateMaxDetectionSlot(name: str, folder):
    '''This function creates the BlockTyp that returns the speed peak value.'''

    assert type(name) == str, "name should be string not "+ str(type(name))
    assert folder.GetClassName() in ["IntFolder","IntPrjfolder"], "Given folder is not folder."

    equation_list = ["inc(max_speed) = speed_in",\
                    "inc(peak_speed) = speed_in",\
                    "inc(sig1) = speed_in",\
                    "inc(sig2) = speed_in",\
                    "inc(sig3) = speed_in",\
                    "inc(sig4) = speed_in",\
                    "inc(sig5) = speed_in",\
                    "sig1 = lastvalue(sig2)",\
                    "sig2 = lastvalue(sig3)",\
                    "sig3 = lastvalue(sig4)",\
                    "sig4 = lastvalue(sig5)",\
                    "sig5 = lastvalue(speed_in)",\
                    "Last_peak_speed = lastvalue(peak_speed)",\
                    "peak_speed = select(sig1<sig2.and.sig2<sig3.and.sig3>sig4.and.sig4>sig5, sig3, Last_peak_speed)"]
                    # "Last_max_speed = lastvalue(max_speed)",\
                    # "max_speed = select(peak_speed > Last_max_speed, peak_speed, Last_max_speed)"] #This is where the code for peak speed should go

    Peak_detector = CreateBlkDef(name,folder)
    Peak_detector.SetAttribute("sInput",["speed_in"])
    Peak_detector.SetAttribute("sAddEquat",equation_list)
    Peak_detector.SetAttribute("sOutput",["peak_speed"])

    return(Peak_detector)

def CreateMinDetectionSlot(name: str, folder):
    '''This function creates the BlockTyp that returns the speed troth value.'''

    assert type(name) == str, "name should be string not "+ str(type(name))
    assert folder.GetClassName() in ["IntFolder","IntPrjfolder"], "Given folder is not folder."

    equation_list = ["inc(min_speed) = speed_in",\
                    "inc(trough_speed) = speed_in",\
                    "inc(sig1) = speed_in",\
                    "inc(sig2) = speed_in",\
                    "inc(sig3) = speed_in",\
                    "inc(sig4) = speed_in",\
                    "inc(sig5) = speed_in",\
                    "sig1 = lastvalue(sig2)",\
                    "sig2 = lastvalue(sig3)",\
                    "sig3 = lastvalue(sig4)",\
                    "sig4 = lastvalue(sig5)",\
                    "sig5 = lastvalue(speed_in)",\
                    "Last_trough_speed = lastvalue(trough_speed)",\
                    "trough_speed = select(sig1>sig2.and.sig2>sig3.and.sig3<sig4.and.sig4<sig5, sig3, Last_trough_speed)"]
                    # "Last_min_speed = lastvalue(min_speed)",\
                    # "min_speed = select(trough_speed < Last_min_speed, trough_speed, Last_min_speed)"] #This is where the code for min speed should go

    Peak_detector = CreateBlkDef(name,folder)
    Peak_detector.SetAttribute("sInput",["speed_in"])
    Peak_detector.SetAttribute("sAddEquat",equation_list)
    # Peak_detector.SetAttribute("sOutput",["min_speed"])
    Peak_detector.SetAttribute("sOutput",["trough_speed"])

    return(Peak_detector)

def CreateAmplitudeDetection(name: str, folder):
    '''This function creates the BlockTyp that returns the speed maximum amplitude.'''

    assert type(name) == str, "name should be string not "+ str(type(name))
    assert folder.GetClassName() in ["IntFolder","IntPrjfolder"], "Given folder is not folder."

    # equation_list = ["inc(max_ampl) = 0",\
    #                  "inc(ref_speed) = speed",\
    #                  "inc(nsequential_increases) = 0",\
    #                  "inc(max_nsequential_increases) = 0",\
    #                  "ampl_up = max_speed - ref_speed",\
    #                  "ampl_down = ref_speed - min_speed",\
    #                  "last_max_ampl = lastvalue(max_ampl)",\
    #                  "curr_max_ampl = select(ampl_up > ampl_down, ampl_up, ampl_down)",\
    #                  "last_nsequential_increases = lastvalue(nsequential_increases)", \
    #                  "last_nsequential_increases_add_one = lastvalue(nsequential_increases)+1", \
    #                  "nsequential_increases = select(curr_max_ampl<>last_max_ampl, select(curr_max_ampl>last_max_ampl, last_nsequential_increases_add_one, 0), last_nsequential_increases, select())", \
    #                  "max_nsequential_increases = select(max_nsequential_increases < nsequential_increases, nsequential_increases, lastvalue(max_nsequential_increases))", \
    #                  "max_ampl = select(curr_max_ampl > last_max_ampl, curr_max_ampl, last_max_ampl)"] #This is where the code for min speed should go

    equation_list = ["inc(ampl) = 0",\
                    "inc(ref_speed) = speed",\
                    "inc(nsequential_increases) = 0",\
                    "inc(max_nsequential_increases) = 0",\
                    "inc(max_offset) = 0",\
                    "curr_offset = abs(speed-ref_speed)",\
                    "max_offset = select(curr_offset > lastvalue(max_offset), curr_offset, lastvalue(max_offset))",\
                    "ampl_up = peak_speed - ref_speed",\
                    "ampl_down = ref_speed - trough_speed",\
                    "last_ampl = lastvalue(curr_ampl)",\
                    "curr_ampl = select(ampl_up > ampl_down, ampl_up, ampl_down)",\
                    "last_nsequential_increases = lastvalue(nsequential_increases)",\
                    "last_nsequential_increases_add_one = lastvalue(nsequential_increases)+1",\
                    "nsequential_increases = select(curr_ampl<>last_ampl, select(curr_ampl>last_ampl, last_nsequential_increases_add_one, 0), last_nsequential_increases)",\
                    "max_nsequential_increases = select(lastvalue(max_nsequential_increases) < nsequential_increases, nsequential_increases, lastvalue(max_nsequential_increases))"] #This is where the code for min speed should go

    Peak_detector = CreateBlkDef(name,folder)
    Peak_detector.SetAttribute("sInput",["speed, peak_speed, trough_speed"])
    # Peak_detector.SetAttribute("sInput",["speed, max_speed, min_speed"])
    Peak_detector.SetAttribute("sAddEquat",equation_list)
    Peak_detector.SetAttribute("sOutput",["max_nsequential_increases"])

    return(Peak_detector)

def setupSimulationParams(oComInc, oComSim, FreeRunSettings):
    '''
    The funciton for setting parameters of the simulation during noo contingency oscilatino check.
    '''

    assert(oComInc.GetClassName() == "ComInc"), "Given Argument 'oComInc' is not of type 'ComInc'."
    assert(oComSim.GetClassName() == "ComSim"), "Given Argument 'oComSim' is not of type 'ComSim'."
   
    dtModifier = GetdtUnitModifier(oComInc)

    # Get initial simulation setup
    SimInitSetup = []

    SimInitSetup.append(oComInc.iopt_simscn)
    SimInitSetup.append(oComInc.iopt_sample)
    SimInitSetup.append(oComInc.tstart)
    SimInitSetup.append(oComInc.dtgrd)
    SimInitSetup.append(oComInc.iopt_locref)
    SimInitSetup.append(oComSim.tstop)
    SimInitSetup.append(oComInc.automaticCompilation)

    # Set new simulation setup
    oComInc.iopt_simscn = 0
    oComInc.iopt_sample = 0
    oComInc.tstart = -FreeRunSettings[2]
    oComInc.dtgrd = FreeRunSettings[4]*dtModifier
    oComInc.iopt_loref = 1
    oComSim.tstop = FreeRunSettings[3]
    oComInc.automaticCompilation = 0

    return(SimInitSetup)

def resetInitialSimulaitonParameters(oComInc, oComSim, SimInitSetup):
    oComInc.iopt_simscn = SimInitSetup[0]
    oComInc.iopt_sample = SimInitSetup[1]
    oComInc.tstart = SimInitSetup[2]
    oComInc.dtgrd = SimInitSetup[3]
    oComInc.iopt_loref = SimInitSetup[4]
    oComSim.tstop = SimInitSetup[5]
    oComInc.automaticCompilation = SimInitSetup[6]


def InitialiseNecessaryBlockTypes(SpeedOscDetDynFolder):
    '''
    This function creates the block types needed for oscilation detection of generators.
    '''
    
    #Create needed block types
    SpeedOscDetFrmTypName = "SpeedOscilationDetectionFrameType"
    SpeedMaxDetBlkTypName = "SpeedMaximumDetectionBlockType"
    SpeedMinDetBlkTypName = "SpeedMinimumDetectionBlockType"
    SpeedOffsetTrackingBlkTypName = "SpeedOffsetTrackingBlockType"

    SpeedOscDetFrmTyp = CreateBlkDef(SpeedOscDetFrmTypName, SpeedOscDetDynFolder)
    SpeedMaxDetBlkTyp = CreateMaxDetectionSlot(SpeedMaxDetBlkTypName, SpeedOscDetDynFolder)
    SpeedMinDetBlkTyp = CreateMinDetectionSlot(SpeedMinDetBlkTypName, SpeedOscDetDynFolder)
    OffsetTrackingBlockTyp = CreateAmplitudeDetection(SpeedOffsetTrackingBlkTypName, SpeedOscDetDynFolder)

    SpeedOscDetFrmTyp.SetAttribute("sOutput",["SpeedOscPeaAmplitude"])

    #Create generator slot
    SpeedInputSlot = SpeedOscDetFrmTyp.CreateObject("BlkSlot","machine")
    SpeedInputSlot.SetAttribute("sOutput",["xspeed"])

    #Create max detection Slot
    SpeedMaxDetSlot = SpeedOscDetFrmTyp.CreateObject("BlkSlot","MaxDetection")
    SpeedMaxDetSlot.SetAttribute("pDsl", SpeedMaxDetBlkTyp)

    #Create min detection Slot
    SpeedMinDetSlot = SpeedOscDetFrmTyp.CreateObject("BlkSlot","MinDetection")
    SpeedMinDetSlot.SetAttribute("pDsl", SpeedMinDetBlkTyp)

    #Create maximum amplitude detection Slot
    SpeedMaxAmplDetSlot = SpeedOscDetFrmTyp.CreateObject("BlkSlot","MaxAmplDetection")
    SpeedMaxAmplDetSlot.SetAttribute("pDsl", OffsetTrackingBlockTyp)

    #signal from speed to max
    sig1 = SpeedOscDetFrmTyp.CreateObject("BlkSig","speed")
    sig1.SetAttribute("pnodfrom", SpeedInputSlot)
    sig1.SetAttribute("inodfrom", 0)
    sig1.SetAttribute("pnodto", SpeedMaxDetSlot)
    sig1.SetAttribute("iconto", 1)
    sig1.SetAttribute("inodto", 0)

    #signal from speed to min
    sig2 = SpeedOscDetFrmTyp.CreateObject("BlkSig","speed")
    sig2.SetAttribute("pnodfrom", SpeedInputSlot)
    sig2.SetAttribute("inodfrom", 0)
    sig2.SetAttribute("pnodto", SpeedMinDetSlot)
    sig2.SetAttribute("iconto", 1)
    sig2.SetAttribute("inodto", 0)

    #signal from speed to max ampl
    sig3 = SpeedOscDetFrmTyp.CreateObject("BlkSig","speed")
    sig3.SetAttribute("pnodfrom", SpeedInputSlot)
    sig3.SetAttribute("inodfrom", 0)
    sig3.SetAttribute("pnodto", SpeedMaxAmplDetSlot)
    sig3.SetAttribute("iconto", 1)
    sig3.SetAttribute("inodto", 0)

    #signal from max to max ampl
    sig4 = SpeedOscDetFrmTyp.CreateObject("BlkSig","max")
    sig4.SetAttribute("pnodfrom", SpeedMaxDetSlot)
    sig4.SetAttribute("inodfrom", 0)
    sig4.SetAttribute("pnodto", SpeedMaxAmplDetSlot)
    sig4.SetAttribute("iconto", 1)
    sig4.SetAttribute("inodto", 1)

    #signal from min to max ampl
    sig5 = SpeedOscDetFrmTyp.CreateObject("BlkSig","min")
    sig5.SetAttribute("pnodfrom", SpeedMinDetSlot)
    sig5.SetAttribute("inodfrom", 0)
    sig5.SetAttribute("pnodto", SpeedMaxAmplDetSlot)
    sig5.SetAttribute("iconto", 1)
    sig5.SetAttribute("inodto", 2)

    #signal to output
    sig_out = SpeedOscDetFrmTyp.CreateObject("BlkSig","speed_peak")
    sig_out.SetAttribute("pnodfrom", SpeedMaxDetSlot)
    sig_out.SetAttribute("inodfrom", 0)
    sig_out.SetAttribute("pnodto", SpeedOscDetFrmTyp)
    sig_out.SetAttribute("iconto", 1)
    sig_out.SetAttribute("inodto", 0)

    return(SpeedOscDetFrmTyp, SpeedMaxDetBlkTyp, SpeedMinDetBlkTyp, OffsetTrackingBlockTyp)

## main functions ---------------------

def InitialisationOscilationDetection(app: pf.Application, oComInc: pf.DataObject, oComSim: pf.DataObject, oFolderGrid: pf.DataObject, sGenMon: pf.DataObject, FreeRunSettings: Iterable[Number]):
    assert(isinstance(app, pf.Application)), "Attribute 'app' is not of type powerfactory.Applicaiton."
    assert(isinstance(oComInc, pf.DataObject)), "Attribute 'oComInc' is not of type powerfactory.DataObject."
    assert(isinstance(oComSim, pf.DataObject)), "Attribute 'oComSim' is not of type powerfactory.DataObject."
    assert(isinstance(oFolderGrid, pf.DataObject)), "Attribute 'oFolderGrid' is not of type powerfactory.DataObject."
    assert(oFolderGrid.GetClassName() == "ElmNet"), "Attribute 'oFolderGrid' is not an Object of Class 'ElmNet'"
    assert(isinstance(sGenMon, Iterable)), "Attribute 'sGenMon' is not of type Iterbale."
    for ind, Elm in enumerate(sGenMon):
        assert(isinstance(Elm, pf.DataObject)), f"Attribute 'sGenMon[{ind}]' is not of type powerfactory.DataObject."
        assert(Elm.GetClassName() == "ElmSym"), f"Attribute 'sGenMon[{ind}]' is not of class 'ElmSym'."

    SimInitSetup = setupSimulationParams(oComInc, oComSim, FreeRunSettings)

    #Get dynamic elements folder and create folder for speed oscilation detection
    dyn_folder = app.GetProjectFolder("blk")
    SpeedOscDetDynFolder = dyn_folder.CreateObject("IntFolder", "SpeedOscDetDynTyps")

    SpeedOscDetFrmTyp, SpeedMaxDetBlkTyp, SpeedMinDetBlkTyp, OffsetTrackingBlockTyp = InitialiseNecessaryBlockTypes(SpeedOscDetDynFolder)

    #Create folder for oscilation detectors
    SpeedOscDetElmFolder = oFolderGrid.CreateObject("IntFolder","SpeedOscilationDetectionFrameFolder")
    CurrPrj = app.GetActiveProject()

    sGenOffsetTrackingBlocks = []

    for oGen in sGenMon:
        CurrGenName = oGen.GetAttribute("loc_name")
        CurrFrameName = f"SpeedOscilationDetectionFrame_{CurrGenName}"

        SpeedOscDetFrm = SpeedOscDetElmFolder.CreateObject("ElmComp",CurrFrameName)
        SpeedOscDetFrm.SetAttribute("typ_id", SpeedOscDetFrmTyp)

        SpeedMaxDetBlk = SpeedOscDetFrm.CreateObject("ElmDsl", "SpeedMaximumOscilationDetectionBlock")
        SpeedMaxDetBlk.SetAttribute("typ_id", SpeedMaxDetBlkTyp)

        SpeedMinDetBlk = SpeedOscDetFrm.CreateObject("ElmDsl", "SpeedMinimumOscilationDetectionBlock")
        SpeedMinDetBlk.SetAttribute("typ_id", SpeedMinDetBlkTyp)

        OffsetTrackingBlock = SpeedOscDetFrm.CreateObject("ElmDsl", "SpeedMaximumOscilationAmplitudeDetectionBlock")
        OffsetTrackingBlock.SetAttribute("typ_id", OffsetTrackingBlockTyp)

        pelm_list = [oGen, SpeedMaxDetBlk, SpeedMinDetBlk, OffsetTrackingBlock]
        SpeedOscDetFrm.SetAttribute("pelm",pelm_list)

        sGenOffsetTrackingBlocks.append(OffsetTrackingBlock)
    
    return(SimInitSetup, sGenOffsetTrackingBlocks, SpeedOscDetDynFolder, SpeedOscDetElmFolder)

def CheckFreeRunStability_v1(app: pf.Application, oFolderGrid: pf.DataObject, FreeRunSettings: Iterable[Number]) -> bool:
    '''
    Run the free run stability check. I.e. if the system is stable is no contingencies are simulated.

    :param app: The PowerFactory application object with the desired project activated.
    :param oFolderGrid: The Folder in which the dynamic model elements should be created.
    :param SimulationSettings: A Iterable contataining settings for the free run procedure
        :param SimulationSettings[0]: The speed at which the FreeRun oscillations are consideered unstable. (in pu)
        :param SimulationSettings[1]: The maximum number of permissible subsequent oscillations with increaing amplitude.
        :param SimulationSettings[2]: The starting time of the simulation (in s)
        :param SimulationSettings[3]: The stopping time for the simulation (in s)
        :param SimulationSettings[4]: The The simulation step size (in s)
    '''

    assert(isinstance(app, pf.Application)), "Attribute 'app' is not of type powerfactory.Applicaiton."
    assert(isinstance(oFolderGrid, pf.DataObject)), "Attribute 'oFolderGrid' is not of type powerfactory.DataObject."
    assert(oFolderGrid.GetClassName() == "ElmNet"), "Attribute 'oFolderGrid' is not an Object of Class 'ElmNet'."
    assert(isinstance(FreeRunSettings, Iterable)), "Attribute 'FreeRunSettings' is not of type Iterable."
    for ind, num in enumerate(FreeRunSettings):
        assert(isinstance(num, Number)), f"Attribute 'FreeRunSettings[{ind}] is not of type Number."
    
    sGenAll = app.GetCalcRelevantObjects("*.ElmSym")
    sGenAct = []
    for oGen in sGenAll:
        if oGen.GetAttribute("outserv") == 0:
            sGenAct.append(oGen)

    oComInc = app.GetFromStudyCase("ComInc")
    oComSim = app.GetFromStudyCase("ComSim")

    SimInitSetup, sGenOffsetTrackingBlocks, SpeedOscDetDynFolder, SpeedOscDetElmFolder = InitialisationOscilationDetection(app, oComInc, oComSim, oFolderGrid, sGenAct, FreeRunSettings)

    oComInc.Execute()
    oComSim.Execute()

    #Check CutoffStability
    CutoffStable = False

    MaxOffsetVals1 = []

    for oGenOffsetTrackingBlock in sGenOffsetTrackingBlocks:
        currMaxOffset = oGenOffsetTrackingBlock.GetAttribute("s:max_offset")
        MaxOffsetVals1.append(currMaxOffset)

    if all(x < FreeRunSettings[0] for x in MaxOffsetVals1):
        CutoffStable = True

    #Check Oscillatory Stability
    OscillatoryStable = False

    NOscillattoryVals1 = []

    for oGenOffsetTrackingBlock in sGenOffsetTrackingBlocks:
        currMaxNIncrOscill = oGenOffsetTrackingBlock.GetAttribute("s:max_nsequential_increases")
        NOscillattoryVals1.append(currMaxNIncrOscill)
        
    if all(x < FreeRunSettings[1] for x in NOscillattoryVals1):
        OscillatoryStable = True

    if CutoffStable and OscillatoryStable:
        resetInitialSimulaitonParameters(oComInc, oComSim, SimInitSetup)
        SpeedOscDetElmFolder.Delete()
        SpeedOscDetDynFolder.Delete()
        return(True)
    else:
        if not CutoffStable:
            print(f"Signal with offset larger than {FreeRunSettings[0]} found.")
            logging.warning(f"Signal with offset larger than {FreeRunSettings[0]} found.")
        if not OscillatoryStable:
            print(f"Signal with more than {FreeRunSettings[1]} subsequent increasing oscillations found.")
            logging.warning(f"Signal with more than {FreeRunSettings[1]} subsequent increasing oscillations found.")

        return(False)