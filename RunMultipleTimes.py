'''
Author: Matjaz Skrlec
date: xx. xx. 20xx
version: x.x
description: This is the description of some code
'''


#--------------------------------------------------------------------------------------------------
## imports
import os
import sys
from dotenv import load_dotenv
load_dotenv()
import time
import logging
import subprocess
import shutil
from pathlib import Path

def MoveFile(old_file_path: Path, file_dir: Path, new_file_name: str):
    '''
    This function copys a file to another directory, and changes its name to a desired name. If the name already exists, it appends a number. 
    '''
    assert(isinstance(old_file_path, Path)), "Argument 'old_file_pathe' must be class Path"
    assert(isinstance(file_dir, Path)), "Argument 'file_dir' must be class Path"
    assert(isinstance(new_file_name, str)), "Argument 'new_file_name' must be class str"

    ID_number = 0
    main_file_full_path = file_dir / new_file_name
    destination = main_file_full_path.with_stem(f"{main_file_full_path.stem}_{ID_number}")

    while destination.exists():
        print(f"File path {destination} already exists. Creating new filepath.")
        logging.warning(f"File path {destination} already exists. Creating new filepath.")
        ID_number += 1
        destination = main_file_full_path.with_stem(f"{main_file_full_path.stem}_{ID_number}")
        print(f"New file path is {destination}")
        logging.warning(f"New file path is {destination}")

    shutil.copy2(old_file_path, destination)
    old_file_path.unlink()

if __name__ == "__main__":
    # variable parameters 
    ## number of iterations   
    n_iterations = 10
    
    ## maximum_waiting_time_for_one_iteration
    max_wait_process_h = 0 # hours
    max_wait_process_m = 10 # minutes
    max_wait_process_s = 0 # seconds

    ## Flag for type of saving results
    MainDirSaveFlag = int(os.getenv("MainDirSaveFlag"))

    ## maximum number of rows in a single main file. Only used if MainDirSaveFlag == 0
    max_main_n_rows = 50

    ## Loadflow main file, results are saved to.
    vault_directory = "results\\vault" # the directory the result files are ultimately moved to
    vault_directory_Path = Path(vault_directory)

    Info_main_file = (os.getenv("Main_Info"))
    Info_main_file_Path = Path(Info_main_file)
    New_Info_main_file = "Info_main.csv"

    LF_main_file = (os.getenv("Main_LF"))
    LF_main_file_Path = Path(LF_main_file)
    New_LF_main_file = "LF_main.csv"

    TSA_main_file = (os.getenv("Main_TSA"))
    TSA_main_file_Path = Path(TSA_main_file)
    New_TSA_main_file = "TSA_main.csv"

    FSA_main_file = (os.getenv("Main_FSA"))
    FSA_main_file_Path = Path(FSA_main_file)
    New_FSA_main_file = "FSA_main.csv"

    SSSA_main_file = (os.getenv("Main_SSSA"))
    SSSA_main_file_Path = Path(SSSA_main_file)
    New_SSSA_main_file = "SSSA_main.csv"

    # define the 'fullDSA' and 'ClearPfSpace' commands to run
    python = sys.executable
    cmd_run_fullDSA = [python, 'fullDSA.py']
    cmd_run_ClearPfSpace = [python, 'ClearPfSpace.py']

    # get time for timing purpose
    time_start = time.time()

    for i in range(n_iterations):
        time_iter_start = time.time()
        # setup logger
        logFile = f"logger\\File_running_log.log"
        logging.basicConfig(filename = logFile, filemode = "a", level = logging.INFO)
        logging.info(f"Calculation of iteration {i+1}.")


        # define subprocesses for fullDSA.py and CreaPfSpace.py
        timeout_s = 3600*max_wait_process_h + 60*max_wait_process_m + max_wait_process_s
        p = subprocess.Popen(cmd_run_fullDSA, stderr=subprocess.PIPE)

        try:
            print("Executing script fullDSA.py")
            logging.info("Executing script fullDSA.py")
            p.wait(timeout=timeout_s)
            print("Returning script fullDSA.py")
            logging.info("Returning script fullDSA.py")
            stdout, stderr = p.communicate()
            p2 = subprocess.Popen(cmd_run_ClearPfSpace)
            p2.wait(timeout=60)
            if p.returncode != 0: # record errors in log file
                print(f"Process failed with error: {stderr}")
                print(f"The return code of the process was {p.returncode}")
                logging.warning(f"Process failed with error: {stderr}")
                logging.warning(f"The return code of the process was {p.returncode}")
            else:
                print("Process completed successfully.")
                logging.info("Process completed successfully.")

        except subprocess.TimeoutExpired:
            print("Process took too long an was terminated.")
            logging.warning("Process took too long an was terminated.")
            p.terminate()
            time.sleep(2)
            p.kill()
            p2.wait(timeout=60)
        time_end_iter = time.time()

        if MainDirSaveFlag == 0:
            if LF_main_file_Path.exists():
                with open(LF_main_file_Path, 'r') as f:
                    lines = f.readlines()
                if len(lines) >= max_main_n_rows:
                    MoveFile(Info_main_file_Path, vault_directory_Path, New_Info_main_file)
                    MoveFile(LF_main_file_Path, vault_directory_Path, New_LF_main_file)
                    MoveFile(TSA_main_file_Path, vault_directory_Path, New_TSA_main_file)
                    MoveFile(FSA_main_file_Path, vault_directory_Path, New_FSA_main_file)
                    MoveFile(SSSA_main_file_Path, vault_directory_Path, New_SSSA_main_file)
            
        print(f'Time for analysis in iteration {i} was {time_end_iter-time_iter_start} s.')
        logging.info(f'Time for analysis in iteration {i} was {time_end_iter-time_iter_start} s.')
        total_time = time_end_iter-time_start
        time_hours = total_time // 3600 #seconds
        time_minutes = (total_time % 3600) // 60
        time_seconds = total_time % 60
        print(f'Total time elapsed {time_hours}h {time_minutes}m {time_seconds:.2f}s.')
        logging.info(f'Total time elapsed {time_hours}h {time_minutes}m {time_seconds:.2f}s.')
        logging.shutdown()

