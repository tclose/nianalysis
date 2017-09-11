from abc import ABCMeta, abstractmethod
from itertools import chain
from nipype.interfaces.io import IOBase, add_traits
from nipype.interfaces.base import (
    DynamicTraitedSpec, traits, TraitedSpec, BaseInterfaceInputSpec,
    Undefined, isdefined, File, Directory)
from nianalysis.nodes import Node
from nianalysis.dataset import Dataset, DatasetSpec
from nianalysis.exceptions import NiAnalysisError
from nianalysis.utils import INPUT_SUFFIX, OUTPUT_SUFFIX


class Archive(object):
    """
    Abstract base class for all Archive systems, DaRIS, XNAT and local file
    system. Sets out the interface that all Archive classes should implement.
    """

    __metaclass__ = ABCMeta

    @abstractmethod
    def source(self, project_id, input_datasets, name=None, study_name=None):
        """
        Returns a NiPype node that gets the input data from the archive
        system. The input spec of the node's interface should inherit from
        ArchiveSourceInputSpec

        Parameters
        ----------
        project_id : str
            The ID of the project to return the sessions for
        input_datasets : list[Dataset]
            An iterable of nianalysis.Dataset objects, which specify the
            datasets to extract from the archive system for each session
        name : str
            Name of the NiPype node
        study_name: str
            Prefix used to distinguish datasets generated by a particular
            study. Used for processed datasets only
        """
        if name is None:
            name = "{}_source".format(self.type)
        source = Node(self.Source(), name=name)
        source.inputs.project_id = str(project_id)
        source.inputs.datasets = [s.to_tuple() for s in input_datasets]
        if study_name is not None:
            source.inputs.study_name = study_name
        return source

    @abstractmethod
    def sink(self, project_id, output_datasets, multiplicity='per_session',
             name=None, study_name=None):
        """
        Returns a NiPype node that puts the output data back to the archive
        system. The input spec of the node's interface should inherit from
        ArchiveSinkInputSpec

        Parameters
        ----------
        project_id : str
            The ID of the project to return the sessions for
        output_datasets : List[BaseFile]
            An iterable of nianalysis.Dataset objects, which specify the
            datasets to extract from the archive system for each session
        name : str
            Name of the NiPype node
        study_name: str
            Prefix used to distinguish datasets generated by a particular
            study. Used for processed datasets only

        """
        if multiplicity.startswith('per_session'):
            sink_class = self.Sink
        elif multiplicity.startswith('per_subject'):
            sink_class = self.SubjectSink
        elif multiplicity.startswith('per_visit'):
            sink_class = self.VisitSink
        elif multiplicity.startswith('per_project'):
            sink_class = self.ProjectSink
        else:
            raise NiAnalysisError(
                "Unrecognised multiplicity '{}' can be one of '{}'"
                .format(multiplicity,
                        "', '".join(Dataset.MULTIPLICITY_OPTIONS)))
        if name is None:
            name = "{}_{}_sink".format(self.type, multiplicity)
        # Ensure iterators aren't exhausted
        output_datasets = list(output_datasets)
        sink = Node(sink_class(output_datasets), name=name)
        sink.inputs.project_id = str(project_id)
        sink.inputs.datasets = [s.to_tuple() for s in output_datasets]
        if study_name is not None:
            sink.inputs.study_name = study_name
        return sink

    @abstractmethod
    def project(self, project_id, subject_ids=None, visit_ids=None):
        """
        Returns a nianalysis.archive.Project object for the given project id,
        which holds information on all available subjects, sessions and
        datasets in the project.

        Parameters
        ----------
        project_id : str
            The ID of the project to return the sessions for
        subject_ids : list(str)
            List of subject ids to filter the returned subjects. If None all
            subjects will be returned.
        visit_ids : list(str)
            List of visit ids to filter the returned sessions. If None all
            sessions will be returned
        """


class ArchiveSourceInputSpec(TraitedSpec):
    """
    Base class for archive source input specifications. Provides a common
    interface for 'run_pipeline' when using the archive source to extract
    primary and preprocessed datasets from the archive system
    """
    project_id = traits.Str(  # @UndefinedVariable
        mandatory=True,
        desc='The project ID')
    subject_id = traits.Str(mandatory=True, desc="The subject ID")
    visit_id = traits.Str(mandatory=True, usedefult=True,
                            desc="The visit or processed group ID")
    datasets = traits.List(
        DatasetSpec.traits_spec(),
        desc="Names of all datasets that comprise the (sub)project")
    study_name = traits.Str(desc=("Prefix prepended onto processed dataset "
                                  "names"))


class ArchiveSource(IOBase):

    __metaclass__ = ABCMeta

    output_spec = DynamicTraitedSpec
    _always_run = True

    def __init__(self, infields=None, outfields=None, **kwargs):
        """
        Parameters
        ----------
        infields : list of str
            Indicates the input fields to be dynamically created

        outfields: list of str
            Indicates output fields to be dynamically created

        See class examples for usage

        """
        if not outfields:
            outfields = ['outfiles']
        super(ArchiveSource, self).__init__(**kwargs)
        undefined_traits = {}
        # used for mandatory inputs check
        self._infields = infields
        self._outfields = outfields
        if infields:
            for key in infields:
                self.inputs.add_trait(key, traits.Any)
                undefined_traits[key] = Undefined

    @abstractmethod
    def _list_outputs(self):
        pass

    def _add_output_traits(self, base):
        return add_traits(base, [dataset[0] + OUTPUT_SUFFIX
                                 for dataset in self.inputs.datasets])


class BaseArchiveSinkInputSpec(DynamicTraitedSpec, BaseInterfaceInputSpec):
    """
    Base class for archive sink input specifications. Provides a common
    interface for 'run_pipeline' when using the archive save
    processed datasets in the archive system
    """
    project_id = traits.Str(  # @UndefinedVariable
        mandatory=True,
        desc='The project ID')  # @UndefinedVariable @IgnorePep8

    name = traits.Str(  # @UndefinedVariable @IgnorePep8
        mandatory=True, desc=("The name of the processed data group, e.g. "
                              "'tractography'"))
    description = traits.Str(mandatory=True,  # @UndefinedVariable
                             desc="Description of the study")
    datasets = traits.List(
        DatasetSpec.traits_spec(),
        desc="Names of all datasets that comprise the (sub)project")
    # TODO: Not implemented yet
    overwrite = traits.Bool(  # @UndefinedVariable
        False, mandatory=True, usedefault=True,
        desc=("Whether or not to overwrite previously created sessions of the "
              "same name"))
    study_name = traits.Str(desc=("Study name to partition processed datasets "
                                  "by"))

    def __setattr__(self, name, val):
        # Need to check whether datasets is not empty, as it can be when
        # unpickling
        if (isdefined(self.datasets) and self.datasets and
                not hasattr(self, name)):
            accepted = [s[0] + INPUT_SUFFIX for s in self.datasets]
            assert name in accepted, (
                "'{}' is not a valid input filename for '{}' archive sink "
                "(accepts '{}')".format(name, self.name,
                                        "', '".join(accepted)))
        super(BaseArchiveSinkInputSpec, self).__setattr__(name, val)


class ArchiveSinkInputSpec(BaseArchiveSinkInputSpec):

    subject_id = traits.Str(mandatory=True, desc="The subject ID"),
    visit_id = traits.Str(mandatory=False,
                            desc="The session or processed group ID")


class ArchiveSubjectSinkInputSpec(BaseArchiveSinkInputSpec):

    subject_id = traits.Str(mandatory=True, desc="The subject ID")


class ArchiveVisitSinkInputSpec(BaseArchiveSinkInputSpec):

    visit_id = traits.Str(mandatory=True, desc="The visit ID")


class ArchiveProjectSinkInputSpec(BaseArchiveSinkInputSpec):
    pass


class BaseArchiveSinkOutputSpec(TraitedSpec):

    out_files = traits.List(
        traits.Either(File(exists=True), Directory(exists=True)),
        desc='datasink outputs')


class ArchiveSinkOutputSpec(BaseArchiveSinkOutputSpec):

    project_id = traits.Str(desc="The project ID")
    subject_id = traits.Str(desc="The subject ID")
    visit_id = traits.Str(desc="The visit ID")


class ArchiveSubjectSinkOutputSpec(BaseArchiveSinkOutputSpec):

    project_id = traits.Str(desc="The project ID")
    subject_id = traits.Str(desc="The subject ID")


class ArchiveVisitSinkOutputSpec(BaseArchiveSinkOutputSpec):

    project_id = traits.Str(desc="The project ID")
    visit_id = traits.Str(desc="The visit ID")


class ArchiveProjectSinkOutputSpec(BaseArchiveSinkOutputSpec):

    project_id = traits.Str(desc="The project ID")


class BaseArchiveSink(IOBase):

    __metaclass__ = ABCMeta

    def __init__(self, output_datasets, **kwargs):
        """
        Parameters
        ----------
        infields : list of str
            Indicates the input fields to be dynamically created

        outfields: list of str
            Indicates output fields to be dynamically created

        See class examples for usage

        """
        super(BaseArchiveSink, self).__init__(**kwargs)
        # used for mandatory inputs check
        self._infields = None
        self._outfields = None
        add_traits(self.inputs, [s.name + INPUT_SUFFIX
                                 for s in output_datasets])

    @abstractmethod
    def _base_outputs(self):
        "List the base outputs of the sink interface, which relate to the "
        "session/subject/project that is being sunk"


class ArchiveSink(BaseArchiveSink):

    input_spec = ArchiveSinkInputSpec
    output_spec = ArchiveSinkOutputSpec

    ACCEPTED_MULTIPLICITIES = ('per_session',)

    def _base_outputs(self):
        outputs = self.output_spec().get()
        outputs['project_id'] = self.inputs.project_id
        outputs['subject_id'] = self.inputs.subject_id
        outputs['visit_id'] = self.inputs.visit_id
        return outputs


class ArchiveSubjectSink(BaseArchiveSink):

    input_spec = ArchiveSubjectSinkInputSpec
    output_spec = ArchiveSubjectSinkOutputSpec

    ACCEPTED_MULTIPLICITIES = ('per_subject',)

    def _base_outputs(self):
        outputs = self.output_spec().get()
        outputs['project_id'] = self.inputs.project_id
        outputs['subject_id'] = self.inputs.subject_id
        return outputs


class ArchiveVisitSink(BaseArchiveSink):

    input_spec = ArchiveVisitSinkInputSpec
    output_spec = ArchiveVisitSinkOutputSpec

    ACCEPTED_MULTIPLICITIES = ('per_visit',)

    def _base_outputs(self):
        outputs = self.output_spec().get()
        outputs['project_id'] = self.inputs.project_id
        outputs['visit_id'] = self.inputs.visit_id
        return outputs


class ArchiveProjectSink(BaseArchiveSink):

    input_spec = ArchiveProjectSinkInputSpec
    output_spec = ArchiveProjectSinkOutputSpec

    ACCEPTED_MULTIPLICITIES = ('per_project',)

    def _base_outputs(self):
        outputs = self.output_spec().get()
        outputs['project_id'] = self.inputs.project_id
        return outputs


class Project(object):

    def __init__(self, project_id, subjects, visits, datasets):
        self._id = project_id
        self._subjects = subjects
        self._visits = visits
        self._datasets = datasets

    @property
    def id(self):
        return self._id

    @property
    def subjects(self):
        return iter(self._subjects)

    @property
    def visits(self):
        return iter(self._visits)

    @property
    def datasets(self):
        return self._datasets

    @property
    def dataset_names(self):
        return (d.name for d in self.datasets)

    def __eq__(self, other):
        if not isinstance(other, Project):
            return False
        return (self._id == other._id and
                self._sessions == other._sessions)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "Subject(id={}, num_subjects={})".format(
            self._id, len(list(self.subjects)))

    def __hash__(self):
        return hash(self._id)


class Subject(object):
    """
    Holds a subject id and a list of sessions
    """

    def __init__(self, subject_id, sessions, datasets):
        self._id = subject_id
        self._sessions = sessions
        self._datasets = datasets
        for session in sessions:
            session.subject = self

    @property
    def id(self):
        return self._id

    @property
    def sessions(self):
        return iter(self._sessions)

    @property
    def datasets(self):
        return self._datasets

    @property
    def dataset_names(self):
        return (d.name for d in self.datasets)

    def __eq__(self, other):
        if not isinstance(other, Subject):
            return False
        return (self._id == other._id and
                self._sessions == other._sessions)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "Subject(id={}, num_sessions={})".format(self._id,
                                                        len(self._sessions))

    def __hash__(self):
        return hash(self._id)


class Visit(object):
    """
    Holds a subject id and a list of sessions
    """

    def __init__(self, visit_id, sessions, datasets):
        self._id = visit_id
        self._sessions = sessions
        self._datasets = datasets
        for session in sessions:
            session.visit = self

    @property
    def id(self):
        return self._id

    @property
    def sessions(self):
        return iter(self._sessions)

    @property
    def datasets(self):
        return self._datasets

    @property
    def dataset_names(self):
        return (d.name for d in self.datasets)

    def __eq__(self, other):
        if not isinstance(other, Subject):
            return False
        return (self._id == other._id and
                self._sessions == other._sessions)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "Subject(id={}, num_sessions={})".format(self._id,
                                                        len(self._sessions))

    def __hash__(self):
        return hash(self._id)


class Session(object):
    """
    Holds the session id and the list of datasets loaded from it

    Parameters
    ----------
    subject_id : str
        The subject ID of the session
    visit_id : str
        The visit ID of the session
    datasets : list(Dataset)
        The datasets found in the session
    processed : Session
        If processed scans are stored in a separate session, it is provided
        here
    """

    def __init__(self, subject_id, visit_id, datasets, processed=None):
        self._subject_id = subject_id
        self._visit_id = visit_id
        self._datasets = datasets
        self._subject = None
        self._visit = None
        self._processed = processed

    @property
    def visit_id(self):
        return self._visit_id

    @property
    def subject_id(self):
        return self._subject_id

    @property
    def subject(self):
        return self._subject

    @subject.setter
    def subject(self, subject):
        self._subject = subject

    @property
    def visit(self):
        return self._visit

    @visit.setter
    def visit(self, visit):
        self._visit = visit

    @property
    def processed(self):
        return self._processed

    @processed.setter
    def processed(self, processed):
        self._processed = processed

    @property
    def acquired(self):
        """True if the session contains acquired scans"""
        return not self._processed or self._processed is None

    @property
    def datasets(self):
        return iter(self._datasets)

    @property
    def dataset_names(self):
        return (d.name for d in self.datasets)

    @property
    def processed_dataset_names(self):
        datasets = (self.datasets
                    if self.processed is None else self.processed.datasets)
        return (d.name for d in datasets)

    @property
    def all_dataset_names(self):
        return chain(self.dataset_names, self.processed_dataset_names)

    def __eq__(self, other):
        if not isinstance(other, Session):
            return False
        return (self.subject_id == other.subject_id and
                self.visit_id == other.visit_id and
                self.datasets == other.datasets and
                self.processed == other.processed)

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return ("Session(subject_id='{}', visit_id='{}', num_datasets={}, "
                "processed={})".format(self.subject_id, self.visit_id,
                                       len(self._datasets), self.processed))

    def __hash__(self):
        return hash((self.subject_id, self.visit_id))
