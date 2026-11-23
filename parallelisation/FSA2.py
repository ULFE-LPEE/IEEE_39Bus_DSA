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
import DSA.FSA as FSA
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

# Get AllRoCoFComp
AllRoCoFComp = ComElm_folder.GetContents()

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

# FSA parameters
ScriptArguments = currentScript.GetAttribute("IntName")
RoCoF_settings_names = []
RoCoF_settings_vals = []

for i in ScriptArguments:
    if "RoCoF_setting" in i:
        RoCoF_settings_names.append(i)
        app.PrintInfo("To se izvede")
        RoCoF_settings_vals.append(currentScript.GetAttribute(i))

iprint = True
logging.info("--------------------------- Running TSAForTermAtSingleGenerator ---------------------------")
execStart = time.time()
FSAInfo = FSA.FSASingleGenerator2(app, RoCoF_settings_vals, AllRoCoFComp, generator, iprint) # izracun samo na enem generatorju
execEnd = time.time()

# Prepare data for saving to temporary file (pf.DataObjects will be saves as strings: e.g. "Bus 02.ElmTerm")
if (FSAInfo is not None):
    logging.info(f"FSA results that will be saved to temp files: {FSAInfo}")
    try:
        HandleFiles.saveResultsToTemporaryFileFSA(FSAInfo, f"FSAdata_{generatorName}")
    except Exception as e:
        logging.error(f"Failed to save results for {generatorName}: {e}")
else:
    logging.warning(f"FSA did not return FSA info for generator {generatorName}.")

logging.info(f"Script Execution time: {execEnd - execStart} seconds")