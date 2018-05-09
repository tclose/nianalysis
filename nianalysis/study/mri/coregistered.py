from nipype.interfaces.fsl import FLIRT
from nipype.interfaces.spm.preprocess import Coregister
from nianalysis.requirement import fsl5_req
from nianalysis.citation import fsl_cite
from nianalysis.requirement import spm12_req
from nianalysis.citation import spm_cite
from nianalysis.data_format import (
    nifti_gz_format, nifti_format, text_matrix_format)
from arcana.study.base import StudyMetaClass, Study
from arcana.dataset import DatasetSpec
from arcana.option import OptionSpec

# class CoregisteredToMatrixStudy(CoregisteredStudy):
#     """
#     Like CoregisteredStudy but in this study the registration matrix is
#     supplied as an input (typically by another sub-study)
#     """
# 
#     __metaclass__ = StudyMetaClass
# 
#     add_data_specs = [
#         DatasetSpec('reference', nifti_gz_format),
#         DatasetSpec('to_register', nifti_gz_format),
#         DatasetSpec('matrix', text_matrix_format),
#         DatasetSpec('registered', nifti_gz_format,
#                     pipeline_name='linear_registration_pipeline')]
# 
#     add_option_specs = [
#         OptionSpec('interpolate', 'trilinear')]
# 
#     _registration_inputs = [DatasetSpec('reference', nifti_gz_format),
#                             DatasetSpec('to_register', nifti_gz_format),
#                             DatasetSpec('matrix', text_matrix_format)]
#     _registration_outputs = [DatasetSpec('registered', nifti_gz_format)]
# 
#     def _fsl_flirt_factory(self, outputs, **kwargs):  # @UnusedVariable @IgnorePep8
#         """
#         Registers a MR scan to a reference MR scan with FSL's FLIRT command
#         using an existing registration matrix
# 
#         Parameters
#         ----------
#         interpolate : str
#             Type of interpolation used. Can be one of 'trilinear',
#             'nearestneighbour', 'sinc', 'spline', None. If None no registration
#             is performed.
# 
#         (NB: see CoregisteredStudy.registration_pipeline for remaining params)
#         """
#         pipeline = super(
#             CoregisteredToMatrixStudy, self)._fsl_flirt_factory(
#                 outputs, **kwargs)
#         flirt = pipeline.node('flirt')
#         if pipeline.option('interpolate') is not None:
#             flirt.inputs.interp = pipeline.option('interpolate')
#             flirt.inputs.apply_xfm = True
#         else:
#             flirt.inputs.apply_xfm = False
#         return pipeline
# 
#     def _spm_coreg_pipeline(self, **kwargs):
#         raise NotImplementedError(
#             "SPM pipeline doesn't have (or at least it isn't implemented in "
#             "Arcana) a registration pipeline")
# 
#     def _connect_matrix(self, pipeline, flirt):
#         pipeline.connect_input('matrix', flirt, 'in_matrix_file')
