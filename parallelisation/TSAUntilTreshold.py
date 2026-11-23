import sys, os

# Import the venv to use the packages installed in it. #! THE COMMAND MUST BE IN LINE 4! DO NOT CHANGE IT
venv_path = 'path/to/your/venv' # this row is set automatically when you run fullDSA.py
if os.path.exists(venv_path) and venv_path not in sys.path:
    sys.path.insert(0, venv_path)

# Add the parent directory to the system path to import modules from it
sys.path.append(os.path.join(os.getcwd(), "..")) 

from dotenv import load_dotenv
load_dotenv()

powerfactory_path = os.getenv("PowerfactoryPyFilePath")
if powerfactory_path:
    sys.path.append(powerfactory_path)
else:
    raise ValueError("Environment variable 'PowerfactoryPyFilePath' is not set.")

import powerfactory as pf
from powerfactory import DataObject
import time
import logging
import PFSupport.GetElements as GetElements
import DSA.TSA as TSA
import DSA.HandleFiles as HandleFiles

# Start PF in non-interactive mode
app = pf.GetApplicationExt()

# Extract PF ComPython script data
currentScript = app.GetCurrentScript()
generator: DataObject = currentScript.GetAttribute("generatorInput")
ComElm_folder: DataObject = currentScript.GetAttribute("ComElm_folder")

if generator.GetAttribute("for_name"):
    generatorName: str = generator.GetAttribute("for_name")
else:
    generatorName: str = generator.GetAttribute("loc_name")
if ":" in generatorName:
    index = generatorName.find(":")
    generatorName = generatorName[index+1:]
NcontingencyGrids = len(currentScript.GetAttribute("obj_name"))-2
contingencyGrids = []
for i in range(NcontingencyGrids):
    currContingenyGrid = currentScript.GetAttribute(f"ContingencyGrid_{i}")
    contingencyGrids.append(currContingenyGrid)

# Get OOSDetFrm and create sGenAng
ComElm_folder_Elms = ComElm_folder.GetContents()
sGenAng = []

for oElm in ComElm_folder_Elms:
    if "OOSDetection" in oElm.GetAttribute("loc_name"):
        OOSDetFrm = oElm
    else:
        AngAdderElements = oElm.GetAttribute("pelm")
        sGenAng.append([AngAdderElements[0], oElm])

# Setup logFile and logging configuration
log_dir = ".\\logger"
os.makedirs(log_dir, exist_ok=True) # Create the directory if it doesn't exist
#check if logging file already exists
file_indexing = 0
logFile = os.path.join(log_dir, f"log_SC_at_{generatorName}_{file_indexing}.log")
while os.path.exists(logFile):
    file_indexing = file_indexing+1
    logFile = os.path.join(log_dir, f"log_SC_at_{generatorName}_{file_indexing}.log")
t_program_start = time.time()
logging.basicConfig(
    filename=logFile,
    filemode="a",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# TSA parameters
tStartTSA = currentScript.GetAttribute("tStartTSA")
tStopTSA = currentScript.GetAttribute("tStopTSA")
tSimStepTSA = currentScript.GetAttribute("tSimStepTSA")
tMaxClear = currentScript.GetAttribute("tMaxClear")
tMinClear = currentScript.GetAttribute("tMinClear")
tStepTSA = currentScript.GetAttribute("tStepTSA")
TSA_settings = [tStartTSA, tStopTSA, tSimStepTSA, tMaxClear, tMinClear, tStepTSA]
CCT_treshold = currentScript.GetAttribute("CCT_treshold")
nRecord = currentScript.GetAttribute("nRecord")

iprint = True
logging.info("--------------------------- Running TSAForTermAtSingleGenerator ---------------------------")
execStart = time.time()
cctInfo = TSA.TSAUntilTresholdSingleGenerator(app, TSA_settings, CCT_treshold, nRecord, OOSDetFrm, sGenAng, generator, contingencyGrids, iprint) # izracun samo na generatorskih zbiralkah
execEnd = time.time()

# Prepare data for saving to temporary file (pf.DataObjects will be saves as strings: e.g. "Bus 02.ElmTerm")
if (cctInfo is not None):
    cctInfoToSave = cctInfo.copy()
    logging.info(f"cct results that will be saved to temp files: {cctInfoToSave}")
    try:
        HandleFiles.saveResultsToTemporaryFileTSA(cctInfoToSave, f"cctInfo_{generatorName}")
    except Exception as e:
        logging.error(f"Failed to save results for {generatorName}: {e}")
else:
    logging.warning(f"TSA did not return CCT info for generator {generatorName}.")

logging.info(f"Script Execution time: {execEnd - execStart} seconds")