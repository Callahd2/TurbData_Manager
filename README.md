
# TurbData Manager (TDM)

**TurbData Manager (TDM)** is a Python-based application for managing **large-scale turbulence datasets** from the [Johns Hopkins Turbulence Database (JHTDB)](http://turbulence.pha.jhu.edu/).  
It provides a **PyQt6 graphical interface** and a modular backend that enables researchers and engineers to query, organize, and resume downloads of multi-gigabyte datasets for **CFD and machine learning research**.


**Pre-Release Notice**  
This project is currently in **pre-release development**.  
It is not production ready, and features may change significantly before the first stable release.

**Authentication**
An API token is **required** to use the JHTDB.  
This project does **not** provide one — you must request your own from the [Johns Hopkins Turbulence Database](http://turbulence.pha.jhu.edu/).  
Once obtained, enter your token into the GUI when prompted.


## Features

- **PyQt6 GUI** for intuitive dataset creation, browsing, and file management
- **Resumable queries**: pause/resume long dataset downloads without data loss
- **Chunked queries** with adaptive retry logic to handle JHTDB limits
- **HDF5-ready storage structure** for scalable ML pipelines
- **Metadata-driven design**: dataset constraints, grid configs, and runtime configs are all serialized for reproducibility
- **Flexible session management**:
  - Create new dataset series with custom grid/time bounds
  - Load existing sessions and continue querying
  - Maintain a searchable log of all datasets

## Attribution
This project makes use of the Johns Hopkins Turbulence Database (JHTDB) 
API and related tools, © Johns Hopkins University. Those components are 
licensed separately under the Apache License, Version 2.0. All rights to 
JHTDB code remain with their original authors.




# Installation
```bash
# Clone the repository
git clone https://github.com/<your-username>/TurbData-Toolkit.git
cd TurbData-Toolkit

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # (Linux/Mac)
.venv\Scripts\activate      # (Windows)

# Install dependencies
pip install -r requirements.txt

# Run the GUI
python src/Controllers/MainWindowController.py


==============================================
==	      Project Structure                 ==
==============================================
TurbData-Manager/
├── src/                    # Source code
│   ├── Controllers/        # PyQt6 GUI controllers
│   │   ├── MainWindowController.py
│   │   ├── NewSessionDialog.py
│   │   └── LoadSessionDialog.py
│   ├── main/            # Core logic
│   │   ├── query_manager.py
│   │   ├── file_manager.py
│   │   ├── supplementary_classes.py
│   │   └── query_session.py
│   └── ui/                 # Qt Designer UI files (or generated Python)
├── examples/               # Demo scripts (coming soon)
├── docs/                   # Documentation (coming soon)
├── requirements.txt        # Python dependencies
├── LICENSE                 # License file
└── README.md               # This file
