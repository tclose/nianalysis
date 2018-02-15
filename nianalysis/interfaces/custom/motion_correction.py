from __future__ import absolute_import
from nipype.interfaces.base import (BaseInterface, BaseInterfaceInputSpec,
                                    traits, File, TraitedSpec, Directory)
import numpy as np
from nipype.utils.filemanip import split_filename
import os
import glob
import shutil
import nibabel as nib
from nipype.interfaces.base import isdefined
import scipy.ndimage.measurements as snm


class MotionMatCalculationInputSpec(BaseInterfaceInputSpec):

    reg_mat = File(exists=True, desc='Registration matrix', mandatory=True)
    qform_mat = File(exists=True, desc='Qform matrix', mandatory=True)
    align_mats = Directory(exists=True, desc='Directory with intra-scan '
                           'alignment matrices', default=None)


class MotionMatCalculationOutputSpec(TraitedSpec):

    motion_mats = Directory(exists=True, desc='Directory with resultin motion'
                            ' matrices')


class MotionMatCalculation(BaseInterface):

    input_spec = MotionMatCalculationInputSpec
    output_spec = MotionMatCalculationOutputSpec

    def _run_interface(self, runtime):

        reg_mat = np.loadtxt(self.inputs.reg_mat)
        qform_mat = np.loadtxt(self.inputs.qform_mat)
        _, out_name, _ = split_filename(self.inputs.reg_mat)
        if self.inputs.align_mats:
            list_mats = sorted(glob.glob(self.inputs.align_mats+'/MAT*'))
            if not list_mats:
                raise Exception(
                    'Folder {} is empty!'.format(self.inputs.align_mats))
            for mat in list_mats:
                m = np.loadtxt(mat)
                concat = np.dot(reg_mat, m)
                self.gen_motion_mat(concat, qform_mat, mat)
            mat_path, _, _ = split_filename(mat)
            mm = glob.glob(mat_path+'/*motion_mat*.mat')
        else:
            concat = reg_mat[:]
            self.gen_motion_mat(concat, qform_mat, out_name)
            mm = glob.glob('*motion_mat*.mat')
        os.mkdir(out_name)

        for f in mm:
            shutil.move(f, out_name)

        return runtime

    def gen_motion_mat(self, concat, qform, out_name):

        concat_inv = np.linalg.inv(concat)
        concat_inv_qform = np.dot(qform, concat_inv)
        concat_inv_qform_inv = np.linalg.inv(concat_inv_qform)
        np.savetxt('{0}_motion_mat_inv.mat'.format(out_name),
                   concat_inv_qform_inv)
        np.savetxt('{0}_motion_mat.mat'.format(out_name),
                   concat_inv_qform)

    def _list_outputs(self):
        outputs = self._outputs().get()

        _, out_name, _ = split_filename(self.inputs.reg_mat)

        outputs["motion_mats"] = os.path.abspath(out_name)

        return outputs


class MergeListMotionMatInputSpec(BaseInterfaceInputSpec):

    file_list = traits.List(mandatory=True, desc='List of files to merge')


class MergeListMotionMatOutputSpec(TraitedSpec):

    out_dir = Directory(desc='Output directory.')


class MergeListMotionMat(BaseInterface):

    input_spec = MergeListMotionMatInputSpec
    output_spec = MergeListMotionMatOutputSpec

    def _run_interface(self, runtime):

        file_list = self.inputs.file_list
        pth, _, _ = split_filename(file_list[0])
        if os.path.isdir(pth+'/motion_mats') is False:
            os.mkdir(pth+'/motion_mats')
        for f in file_list:
            shutil.copy(f, pth+'/motion_mats')

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()

        file_list = self.inputs.file_list
        pth, _, _ = split_filename(file_list[0])
        outputs["out_dir"] = pth+'/motion_mats'

        return outputs


class PrepareDWIInputSpec(BaseInterfaceInputSpec):

    pe_dir = traits.Str(mandatory=True, desc='Phase encoding direction')
    phase_offset = traits.Str(mandatory=True, desc='phase offset')
    dwi = File(mandatory=True, exists=True)
    dwi1 = File(mandatory=True, exists=True)
    topup = traits.Bool(desc='Specify whether the PrepareDWI output will be'
                        'used for TOPUP distortion correction')


class PrepareDWIOutputSpec(TraitedSpec):

    pe = traits.Str(desc='Phase encoding direction.')
    main = File(desc='4D dwi scan for eddy.')
    secondary = File(desc='3D dwi scan for distortion correction.')
    pe_1 = traits.Str(
        desc='Phase encoding direction second dwi.')


class PrepareDWI(BaseInterface):

    input_spec = PrepareDWIInputSpec
    output_spec = PrepareDWIOutputSpec

    def _run_interface(self, runtime):

        self.dict_output = {}
        pe_dir = self.inputs.pe_dir
        phase_offset = float(self.inputs.phase_offset)
        topup = self.inputs.topup
        dwi = nib.load(self.inputs.dwi)
        dwi = dwi.get_data()
        dwi1 = nib.load(self.inputs.dwi1)
        dwi1 = dwi1.get_data()
        if pe_dir == 'ROW':
            if np.sign(phase_offset) == -1:
                self.dict_output['pe'] = 'RL'
            else:
                self.dict_output['pe'] = 'LR'
        elif pe_dir == 'COL':
            if phase_offset < 1:
                self.dict_output['pe'] = 'AP'
            else:
                self.dict_output['pe'] = 'PA'
        else:
            raise Exception('Phase encoding direction cannot be establish by '
                            'looking at the header. DWI pre-processing will '
                            'not be performed.')
        self.dict_output['pe_1'] = self.dict_output['pe'][::-1]

        if len(dwi.shape) == 4 and len(dwi1.shape) == 3:
            self.dict_output['main'] = self.inputs.dwi
            self.dict_output['secondary'] = self.inputs.dwi1
        elif len(dwi.shape) == 3 and len(dwi1.shape) == 4:
            self.dict_output['main'] = self.inputs.dwi1
            self.dict_output['secondary'] = self.inputs.dwi
        elif len(dwi.shape) == 3 and len(dwi1.shape) == 3:
            self.dict_output['main'] = self.inputs.dwi
            self.dict_output['secondary'] = self.inputs.dwi1
        elif topup and len(dwi1.shape) == 4:
            ref = nib.load(self.inputs.dwi1)
            dwi1_b0 = dwi1[:, :, :, 0]
            im2save = nib.Nifti1Image(dwi1_b0, affine=ref.affine)
            nib.save('b0.nii.gz', im2save)
            self.dict_output['main'] = self.inputs.dwi
            self.dict_output['secondary'] = 'b0.nii.gz'

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()

        outputs["pe"] = self.dict_output['pe']
        outputs["main"] = self.dict_output['main']
        outputs["secondary"] = self.dict_output['secondary']
        if isdefined(self.dict_output['pe_1']):
            outputs["pe_1"] = self.dict_output['pe_1']

        return outputs


class CheckDwiNamesInputSpec(BaseInterfaceInputSpec):

    dicom_dwi = Directory()
    dicom_dwi1 = Directory()
    nifti_dwi = File()


class CheckDwiNamesOutputSpec(TraitedSpec):

    main = Directory()


class CheckDwiNames(BaseInterface):

    input_spec = CheckDwiNamesInputSpec
    output_spec = CheckDwiNamesOutputSpec

    def _run_interface(self, runtime):

        dwi = self.inputs.dicom_dwi
        dwi1 = self.inputs.dicom_dwi1
        nifti = self.inputs.nifti_dwi
        self.dict_output = {}

        if nifti.split('/')[-1].split('.')[0] in dwi:
            self.dict_output['main'] = self.inputs.dicom_dwi
        elif nifti.split('/')[-1].split('.')[0] in dwi1:
            self.dict_output['main'] = self.inputs.dicom_dwi1

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()

        outputs["main"] = self.dict_output['main']

        return outputs


class GenTopupConfigFilesInputSpec(BaseInterfaceInputSpec):

    ped = traits.Str(desc='phase encoding direction for the main image')


class GenTopupConfigFilesOutputSpec(TraitedSpec):

    config_file = File(exists=True, desc='configuration file for topup')
    apply_topup_config = File(
        exists=True, desc='configuration file for apply_topup')


class GenTopupConfigFiles(BaseInterface):

    input_spec = GenTopupConfigFilesInputSpec
    output_spec = GenTopupConfigFilesOutputSpec

    def _run_interface(self, runtime):

        ped = self.inputs.ped

        if ped == 'RL':
            with open('config_file.txt', 'w') as f:
                f.write('-1 0 0 1 \n1 0 0 1')
            f.close()
            with open('apply_topup_config_file.txt', 'w') as f:
                f.write('-1 0 0 1')
            f.close()
        elif ped == 'LR':
            with open('config_file.txt', 'w') as f:
                f.write('1 0 0 1 \n-1 0 0 1')
            f.close()
            with open('apply_topup_config_file.txt', 'w') as f:
                f.write('1 0 0 1')
            f.close()
        elif ped == 'AP':
            with open('config_file.txt', 'w') as f:
                f.write('0 -1 0 1 \n0 1 0 1')
            f.close()
            with open('apply_topup_config_file.txt', 'w') as f:
                f.write('0 -1 0 1')
            f.close()
        elif ped == 'AP':
            with open('config_file.txt', 'w') as f:
                f.write('0 1 0 1 \n0 -1 0 1')
            f.close()
            with open('apply_topup_config_file.txt', 'w') as f:
                f.write('0 1 0 1')
            f.close()

        return runtime

    def _list_outputs(self):
        outputs = self._outputs().get()

        outputs["config_file"] = os.path.join(
            os.getcwd(), 'config_file.txt')
        outputs["apply_topup_config"] = os.path.join(
            os.getcwd(), 'apply_topup_config_file.txt')

        return outputs


class AffineMatrixGenerationInputSpec(BaseInterfaceInputSpec):

    motion_parameters = File(exists=True)
    reference_image = File(exists=True)


class AffineMatrixGenerationOutputSpec(TraitedSpec):

    affine_matrices = Directory(exists=True)


class AffineMatrixGeneration(BaseInterface):

    input_spec = AffineMatrixGenerationInputSpec
    output_spec = AffineMatrixGenerationOutputSpec

    def _run_interface(self, runtime):

        _, out_name, _ = split_filename(self.inputs.motion_parameters)
        motion_par = np.loadtxt(self.inputs.motion_parameters)
        motion_par = motion_par[:, :6]
        ref = nib.load(self.inputs.reference_image)
        ref_data = ref.get_data()
        # centre of mass
        if ref_data.shape == 4:
            com = list(snm.center_of_mass(ref_data[:, :, :, 0]))
        else:
            com = list(snm.center_of_mass(ref_data))

        hdr = ref.header
        resolution = list(hdr.get_zooms()[:3])

        for i in range(len(motion_par)):
            mat = self.create_affine_mat(motion_par[i, :], resolution*com)
            np.savetxt(
                'affine_mat_{}.mat'.format(str(i).zfill(4)), mat, fmt='%f')

        affines = glob.glob('affine_mat*.mat')
        os.mkdir(out_name)
        for f in affines:
            shutil.move(f, out_name)

        return runtime

    def create_affine_mat(self, mp, cog):

        T = np.eye(4)

        T[0, -1] = cog[0]
        T[1, -1] = cog[1]
        T[2, -1] = cog[2]

        T_1 = np.linalg.inv(T)

        tx = mp[0]
        ty = mp[1]
        tz = mp[2]
        rx = mp[3]
        ry = mp[4]
        rz = mp[5]

        Rx = np.eye(3)
        Rx[1, 1] = np.cos(rx)
        Rx[1, 2] = np.sin(rx)
        Rx[2, 1] = -np.sin(rx)
        Rx[2, 2] = np.cos(rx)
        Ry = np.eye(3)
        Ry[0, 0] = np.cos(ry)
        Ry[0, 2] = -np.sin(ry)
        Ry[2, 0] = np.sin(ry)
        Ry[2, 2] = np.cos(ry)
        Rz = np.eye(3)
        Rz[0, 0] = np.cos(rz)
        Rz[0, 1] = np.sin(rz)
        Rz[1, 0] = -np.sin(rz)
        Rz[1, 1] = np.cos(rz)
        R_3x3 = np.dot(np.dot(Rx, Ry), Rz)

        m = np.eye(4)
        m[:3, :3] = R_3x3
        m[0, 3] = tx
        m[1, 3] = ty
        m[2, 3] = tz

        new_orig = np.dot(T, np.dot(m, T_1))[:, -1]

        m[0, 3] = new_orig[0]
        m[1, 3] = new_orig[1]
        m[2, 3] = new_orig[2]

        return m

    def _list_outputs(self):
        outputs = self._outputs().get()

        _, out_name, _ = split_filename(self.inputs.motion_parameters)

        outputs["affine_matrices"] = os.path.abspath(out_name)

        return outputs
