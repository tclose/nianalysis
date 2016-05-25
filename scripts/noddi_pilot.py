#!/usr/bin/env python
import os.path
import shutil
from neuroanalysis import Scan, NODDIDataset, LocalArchive
from neuroanalysis.file_formats import mrtrix_format

ARCHIVE_PATH = os.path.abspath(os.path.join(
    os.environ['HOME'], 'Data', 'MBI', 'noddi_pilot'))
BASE_WORK_PATH = os.path.abspath(os.path.join(
    os.environ['HOME'], 'Data', 'MBI', 'work'))

NODDI_PROJECT = 'noddi-test'
NODDI_SUBJECT = 'PILOT1'
NODDI_SESSION = 'SESSION1'
WORK_PATH = os.path.abspath(os.path.join(BASE_WORK_PATH, 'noddi'))
SESSION_DIR = os.path.join(ARCHIVE_PATH, NODDI_PROJECT,
                           NODDI_SUBJECT, NODDI_SESSION)
DATASET_NAME = 'noddi'

shutil.rmtree(WORK_PATH, ignore_errors=True)
os.makedirs(WORK_PATH)
dataset = NODDIDataset(
    name=DATASET_NAME,
    project_id=NODDI_PROJECT, archive=LocalArchive(ARCHIVE_PATH),
    scans={'low_b_dw_scan': Scan('r_l_noddi_b700_30_directions',
                                 mrtrix_format),
           'high_b_dw_scan': Scan('r_l_noddi_b2000_60_directions',
                                  mrtrix_format),
           'forward_rpe': Scan('r_l_noddi_b0_6', mrtrix_format),
           'reverse_rpe': Scan('l_r_noddi_b0_6', mrtrix_format)})
dataset.brain_mask_pipeline().run(work_dir=WORK_PATH)
