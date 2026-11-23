# IEEE39 BUS DSA PowerFactory

## Overview

This repository contains code developed as part of the AI-ASSIST project, funded by the Slovenian Research and Innovation Agency (ARIS).

The code provides a framework for performing Dynamic Security Assessment (DSA) of power systems modeled in DIgSILENT PowerFactory. It supports the automated import of power system models, the configuration of different operating conditions, and the evaluation of system stability through transient, frequency, and small-signal stability assessments.

By repeatedly executing the assessment process with randomized operating points, the framework enables the generation of datasets containing stability indices under various system conditions. These datasets can subsequently be used for data-driven power system stability analysis, including the development and evaluation of new assessment methods.

## Features

- PowerFactory model import
- Randomization of operating points
- Dynamic Security Assessment (DSA):
  - Transient Stability Assessment (TSA)
  - Frequency Stability Assessment (FSA)
  - Small-Signal Stability Assessment (SSSA)
- Sequential and parallel assessment algorithms
- Automated dataset generation through repeated simulations
- Export of simulation results to CSV files

## Simulation Workflow

The general workflow of the framework consists of the following steps:

1. **Model import** - Import the specified PowerFactory project.
2. **Operating point configuration** - Configure or randomize the operating point of the power system.
3. **Initial assessment** - Perform load-flow calculations and check the system's dynamic stability without contingencies (FreeRun).
4. **Dynamic Security Assessment** - Perform the selected stability assessments:
   - Transient Stability Assessment (TSA)
   - Frequency Stability Assessment (FSA)
   - Small-Signal Stability Assessment (SSSA)
5. **Result export** - Export the calculated stability indices and simulation information to CSV files.
6. **Dataset generation** - Repeat the process for different operating points to generate a dataset.

## Requirements

- Windows operating system
- Python 3.12
- DIgSILENT PowerFactory (version 2024 or 2026 are currently supported)
- Valid PowerFactory license The following modules should be included:
   - Stability Analysis Functions (RMS)
   - Small signal stability Analysis
   - Scripting and Automation (if parallel computing is desired)
- Required Python packages listed in `requirements.txt`

## Installation

### 1. Clone the repository

```powershell
git clone https://github.com/USERNAME/REPOSITORY.git
cd REPOSITORY
```

### 2. Create a virtual environment

```powershell
python -m venv .venv
```

### 3. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 4. Install the dependencies

```powershell
python -m pip install -r requirements.txt
```

### 5. Configure the environment files

Rename the provided example configuration files:
- `.envex` to `.env`
- `PF_example.ini` to `PF.ini`

### 6. Configure the .env file

Open the `.env` file and modify the following parameters:

- `PowerfactoryPyFilePath` - Path to the PowerFactory Python module. Ensure that the Python version matches the version used by your virtual environment.
- `powerfactoryIniFile` - Path to the PowerFactory initialization file.
- `Pfd_file` - Path to the PowerFactory project file (`.pfd`).

If a different PowerFactory model is used, also update:
- `prj_str` - Name of the imported project
- `stud_case` - Name of the study case to activate
- `grid_name` - Name of the grid to analyze

### 7. Configure the PF.ini file

Open the `PF.ini` file and modify the following parameters:

- `pythonVersion` - Python version used
- `conrainer` - PowerFactory license container ID
- `backupDirectory` - PowerFactory backup directory
- `workspaceDirectory` - PowerFactory workspace directory

The recommended backup and workspace directories are located in the project's `Workspace` directory.


## Usage

To run the Dynamic Security Assessment once:

```powershell
python fullDSA.py
```

To run the Dynamic Security Assessment multiple times:

```powershell
python RunMultipleTimes.py
```

## Configuration and Options

The framework provides several configuration parameters for controlling model initialization, operating point randomization, assessment algorithms, and result export.


### Setting up the environment

The `.env` file contains the file paths and parameters used by the different processes.

- `PowerfactoryPyFilePath` - Path to the PowerFactory Python module
- `powerfactoryIniFile` - PowerFactory initialization file
- `PF_Workspace_flag` - Use the default (`0`) or modified (`1`) PowerFactory workspace
- `Pfd_file` - Path to the PowerFactory project file
- `prj_str` - Name of the imported project
- `stud_case` - Name of the study case
- `grid_name` - Name of the grid to analyze
- `MainDirSaveFlag` - Append results to existing files (`0`) or create new files (`1`)
- *Other parameters* - Directories used for saving simulation results

### Running the file multiple times

The `RunMultipleTimes.py` script is used to generate datasets by repeatedly executing the DSA process.

- `n_iterations` - Number of iterations, including failed attempts
- `max_waiting_process_h` - Maximum subprocess execution time in hours
- `max_waiting_process_m` - Maximum subprocess execution time in minutes
- `max_waiting_process_m` - Maximum subprocess execution time in seconds
- `max_main_n_rows` - Maximum number of rows in a dataset file before moving it to the vault directory

*The maximum subprocess execution time is the sum of the specified hours, minutes, and seconds.*

### Running fullDSA.py

The `fullDSA.py` script handles project import, initialization, and the execution of the selected stability assessments.

#### Algorithm Selection

**Algorithm_settings (line 40)** - A tuple of three integers that determine the algorithms used for the individual DSA assessments:

- **Position 0 - Transient Stability:**
  - `0` - Sequential calculation at generator terminals only
  - `1` - Sequential calculation at generator terminals and connected lines
  - `2` - Sequential calculation at generator terminals and nearby elements until the CCT exceeds a predefined threshold
  - `3` - Parallel calculation at generator terminals only
  - `4` - Parallel calculation at generator terminals and nearby elements until the CCT exceeds a predefined threshold or a predefined number of elements has been considered
  - `5` - Parallel calculation at lines near generators that are not radially connected to them
- **Position 1 - Frequency Stability:**
  - `0` - Sequential calculation of generator outages, recording one RoCoF value and M values
  - `1` - Parallel calculation of generator outages, recording one RoCoF value and M values
  - `2` - Parallel calculation of generator outages, recording RoCoF values only
- **Position 2 - Small-Signal Stability:**
  - `0` - Calculate small-signal stability for the current operating point

#### Additional parameters

- `Parallel_algorithm_setitng` - Determines whether transient and frequency stability assessments are calculated in parallel or sequentially
- `randomise_setpoint` - Enables or disables operating point randomization
- `logFile` - Location of the PowerFactory simulation log
- `sTSAGenCCT` - Generators considered when calculating transient stability
- `sTSAGenMon` - Generators whose rotor angles are monitored during transient stability assessment
- `sFSAGenOut` - Generators to disconnect during frequency stability assessment
- `sFSAGenMon` - Generators whose rotor speeds are monitored during frequency stability assessment
- `sFSALodLFDD` - Loads considered for low-frequency demand disconnection
- `sSSSAGenMon` - Generators considered during small-signal stability assessment


### PowerFactory simulation settings

The `DSA/RunDSA.py` script manages the simulations and exports their results.

#### FreeRun simulation

The FreeRun simulation is performed before the stability assessments to check whether the system exhibits dynamic instabilities without contingencies.

- `Freerun_cutoff_threshold` - Maximum permissible speed deviation during a simulation without contingencies
- `max_n_of_increasing_oscillations` - Maximum number of consecutive increasing oscillations
- `tStartFreeRun` - Simulation start time
- `tStopFreeRun` - Simulation end time
- `tSimStepFreeRun` - Simulation time step

#### Transient Stability

- `tStartTSA` - Simulation start time
- `tStopTSA` - Simulation end time
- `tSimStepTSA` - Simulation time step
- `tMaxClear` - Maximum contingency clearing time (upper bisection limit)
- `tMinClear` - Minimum contingency clearing time (lower bisection limit)
- `tStepTSA` - Bisection termination threshold
- `CCT_threshold` - Critical clearing time threshold used by algorithms 2 and 4
- `nRecord` - Maximum depth of elements considered by algorithm 4

#### Frequency Stability

- `tStartFSA` - Simulation start time
- `tStopFSA` - Simulation end time
- `tSimStepFSA` - Simulation time step
- `considerLFDD` - Enables or disables low-frequency demand disconnection
- `LFDDFreq` - Frequency thresholds for load disconnection (pu)
- `LFDDPow` - Load power reduction at the specified frequency thresholds (%)
- `Mlim` - Frequency margin calculation thresholds (pu)
- `RoCoFCalcWindows` - Sliding window widths used for RoCoF calculation

#### Small-Signal Stability

- `saveLeftEV` - Save left eigenvectors (`0` - no, `1` - yes)
- `saveRightEV` - Save right eigenvectors (`0` - no, `1` - yes)
- `saveParticFact` - Save participation factors (`0` - no, `1` - yes)
- `minReal` - Minimum real part of eigenvalues to save
- `maxReal` - Maximum real part of eigenvalues to save
- `minDampFreq` - Minimum damping frequency of eigenvalues to save
- `maxDampFreq` - Maximum damping frequency of eigenvalues to save
- `maxRelDamping` - Maximum relative damping of eigenvalues to save

#### Other settings

- `iprint` - Print additional simulation information for debugging
- `export` - Enable or disable result export

## Input and Output

### Input

The input to the DSA process is a PowerFactory project (`.pfd`) specified in the `.env` file.

For information on the required project configuration, see the **Configuration and Options** section.

### Output

The generated results are exported to CSV files in the corresponding directories:

- `results/TSA/` - Transient stability assessment results
- `results/FSA/` - Frequency stability assessment results
- `results/SSSA/` - Small-signal stability assessment results
- `results/LF/` - Load-flow results
- `results/INFO/` - Simulation information
- `results/LOG/` - Process logging
- `results/temp/` - Temporary assessment results
- `results/temp_results/` - Temporary PowerFactory results
- `results/vault/` - Generated datasets

For a detailed explanation of the structure of the exported files, see `Explenation_of_smaples.docx`.


## Project Structure

```text
FullDSA_IEEE_39_bus_variation/
├── CreateModels/                # PowerFactory model importing module
├── DSA/                         # Modules used for dynamic security assessments
├── grid_model/                  # PowerFactory model to be analysed
├── logger/                      # Logging files
├── parallelisation/             # Modules for task parallelisation 
├── PFSupport/                   # Modules that help with powerfactory API 
├── results/                     # Exported results
│   ├── FSA/                        # Frequency stability assessment results
│   ├── INFO/                       # simulation information
│   ├── LF/                         # LoadFlow results
│   ├── LOG/                        # Process logging
│   ├── SSSA/                       # small signal stability assessment results
│   ├── temp/                       # Temporary assessment results
│   ├── temp_results/               # Temporary PowerFactory results
│   ├── TSA/                        # Transient stability assessment results
│   └── vault/                      # The dataset of results
├── Workspace/                   # PowerFactory Workspace
├── .env                         # Environment variables
├── .gitignore                   # Git exclusion rules
├── ClearPFSpace.py              # Delete projects in PowerFactory Directory
├── fullDSA.py                   # Run full process from importing model to exporting analysis results
├── rabdom_setpoint.py           # Modules used to set a random operating point
├── RunMultipleTimes.py          # Run the fullDSA.py 
├── requirements.txt             # Python dependencies 
├── Explenation_of_smaples.docx  # The explenation of the structure of the resulting files 
└── README.md                    # Project documentation
```

## License

This project is licensed under the MIT License. See the LICENSE file for details.
