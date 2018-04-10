#!/usr/bin/env python

import os
import re
import json
import pytz
import dicom
import string
import tzlocal
import logging
import zipfile
import datetime
import measurement_from_label
from pprint import pprint

logging.basicConfig()
log = logging.getLogger('dicom-mr-classifier')

def get_session_label(dcm):
    """
    Switch on manufacturer and either pull out the StudyID or the StudyInstanceUID
    """
    session_label = ''

    if dcm.get('Manufacturer').find('GE') != -1 and dcm.has_key('StudyID'):
        session_label = dcm.get('StudyID')
    else:
        session_label = dcm.get('StudyInstanceUID')

    return session_label


def validate_timezone(zone):
    # pylint: disable=missing-docstring
    if zone is None:
        zone = tzlocal.get_localzone()
    else:
        try:
            zone = pytz.timezone(zone.zone)
        except pytz.UnknownTimeZoneError:
            zone = None
    return zone


def parse_patient_age(age):
    """
    Parse patient age from string.
    convert from 70d, 10w, 2m, 1y to datetime.timedelta object.
    Returns age as duration in seconds.
    """
    if age == 'None' or not age:
        return None

    conversion = {  # conversion to days
        'Y': 365,
        'M': 30,
        'W': 7,
        'D': 1,
    }
    scale = age[-1:]
    value = age[:-1]
    if scale not in conversion.keys():
        # Assume years
        scale = 'Y'
        value = age

    age_in_seconds = datetime.timedelta(int(value) * conversion.get(scale)).total_seconds()

    # Make sure that the age is reasonable
    if not age_in_seconds or age_in_seconds <= 0:
        age_in_seconds = None

    return age_in_seconds


def timestamp(date, time, timezone):
    """
    Return datetime formatted string
    """
    if date and time and timezone:
        # return datetime.datetime.strptime(date + time[:6], '%Y%m%d%H%M%S')
        return timezone.localize(datetime.datetime.strptime(date + time[:6], '%Y%m%d%H%M%S'), timezone)
    return None


def get_timestamp(dcm, timezone):
    """
    Parse Study Date and Time, return acquisition and session timestamps
    """
    if hasattr(dcm, 'StudyDate') and hasattr(dcm, 'StudyTime'):
        study_date = dcm.StudyDate
        study_time = dcm.StudyTime
    elif hasattr(dcm, 'StudyDateTime'):
        study_date = dcm.StudyDateTime[0:8]
        study_time = dcm.StudyDateTime[8:]
    else:
        study_date = None
        study_time = None

    if hasattr(dcm, 'AcquisitionDate') and hasattr(dcm, 'AcquisitionTime'):
        acquitision_date = dcm.AcquisitionDate
        acquisition_time = dcm.AcquisitionTime
    elif hasattr(dcm, 'AcquisitionDateTime'):
        acquitision_date = dcm.AcquisitionDateTime[0:8]
        acquisition_time = dcm.AcquisitionDateTime[8:]
    else:
        acquitision_date = None
        acquisition_time = None

    session_timestamp = timestamp(dcm.StudyDate, dcm.StudyTime, timezone)
    acquisition_timestamp = timestamp(acquitision_date, acquisition_time, timezone)

    if session_timestamp:
        if session_timestamp.tzinfo is None:
            log.info('no tzinfo found, using UTC...')
            session_timestamp = pytz.timezone('UTC').localize(session_timestamp)
        session_timestamp = session_timestamp.isoformat()
    else:
        session_timestamp = ''
    if acquisition_timestamp:
        if acquisition_timestamp.tzinfo is None:
            log.info('no tzinfo found, using UTC')
            acquisition_timestamp = pytz.timezone('UTC').localize(acquisition_timestamp)
        acquisition_timestamp = acquisition_timestamp.isoformat()
    else:
        acquisition_timestamp = ''
    return session_timestamp, acquisition_timestamp


def get_sex_string(sex_str):
    """
    Return male or female string.
    """
    if sex_str == 'M':
        sex = 'male'
    elif sex_str == 'F':
        sex = 'female'
    else:
        sex = ''
    return sex


def assign_type(s):
    """
    Sets the type of a given input.
    """
    if type(s) == list or type(s) == dicom.multival.MultiValue:
        try:
            return [ int(x) for x in s ]
        except ValueError:
            try:
                return [ float(x) for x in s ]
            except ValueError:
                return [ format_string(x) for x in s if len(x) > 0 ]
    else:
        s = str(s)
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return format_string(s)


def format_string(in_string):
    formatted = re.sub(r'[^\x00-\x7f]',r'', str(in_string)) # Remove non-ascii characters
    formatted = filter(lambda x: x in string.printable, formatted)
    if len(formatted) == 1 and formatted == '?':
        formatted = None
    return formatted


def get_seq_data(sequence, ignore_keys):
    seq_dict = {}
    for seq in sequence:
        for s_key in seq.dir():
            s_val = getattr(seq, s_key, '')
            if type(s_val) is dicom.UID.UID or s_key in ignore_keys:
                continue

            if type(s_val) == dicom.sequence.Sequence:
                _seq = get_seq_data(s_val, ignore_keys)
                seq_dict[s_key] = _seq
                continue

            if type(s_val) == str:
                s_val = format_string(s_val)
            else:
                s_val = assign_type(s_val)

            if s_val:
                seq_dict[s_key] = s_val

    return seq_dict

def get_dicom_header(dcm):
    # Extract the header values
    header = {}
    exclude_tags = ['[Unknown]', 'PixelData', 'Pixel Data',  '[User defined data]', '[Protocol Data Block (compressed)]', '[Histogram tables]', '[Unique image iden]']
    tags = dcm.dir()
    for tag in tags:
        try:
            if (tag not in exclude_tags) and ( type(dcm.get(tag)) != dicom.sequence.Sequence ):
                value = dcm.get(tag)
                if value or value == 0: # Some values are zero
                    # Put the value in the header
                    if type(value) == str and len(value) < 10240: # Max dicom field length
                        header[tag] = format_string(value)
                    else:
                        header[tag] = assign_type(value)
                else:
                    log.debug('No value found for tag: ' + tag)

            if type(dcm.get(tag)) == dicom.sequence.Sequence:
                seq_data = get_seq_data(dcm.get(tag), exclude_tags)
                # Check that the sequence is not empty
                if seq_data:
                    header[tag] = seq_data
        except:
            log.debug('Failed to get ' + tag)
            pass
    log.info('done')
    return header

def get_csa_header(dcm):
    import dicom
    import nibabel.nicom.dicomwrappers
    exclude_tags = ['PhoenixZIP', 'SrMsgBuffer']
    header = {}
    try:
        raw_csa_header = nibabel.nicom.dicomwrappers.SiemensWrapper(dcm).csa_header
        tags = raw_csa_header['tags']
    except:
        log.warning('Failed to parse csa header!')
        return header

    for tag in tags:
        if not raw_csa_header['tags'][tag]['items'] or tag in exclude_tags:
            log.debug('Skipping : %s' % tag)
            pass
        else:
            value = raw_csa_header['tags'][tag]['items']
            if len(value) == 1:
                value = value[0]
                if type(value) == str and ( len(value) > 0 and len(value) < 1024 ):
                    header[format_string(tag)] = format_string(value)
                else:
                    header[format_string(tag)] = assign_type(value)
            else:
                header[format_string(tag)] = assign_type(value)
    log.info('done')

    return header


def dicom_classify(zip_file_path, outbase, timezone):
    """
    Extracts metadata from dicom file header within a zip file and writes to .metadata.json.
    """
    import dicom

    # Check for input file path
    if not os.path.exists(zip_file_path):
        log.debug('could not find %s' %  zip_file_path)
        log.debug('checking input directory ...')
        if os.path.exists(os.path.join('/input', zip_file_path)):
            zip_file_path = os.path.join('/input', zip_file_path)
            log.debug('found %s' % zip_file_path)

    if not outbase:
        outbase = '/flywheel/v0/output'
        log.info('setting outbase to %s' % outbase)

    # Extract the last file in the zip to /tmp/ and read it
    dcm = []
    if zipfile.is_zipfile(zip_file_path):
        zip = zipfile.ZipFile(zip_file_path)
        for n in range((len(zip.namelist()) -1), -1, -1):
            dcm_path = zip.extract(zip.namelist()[n], '/tmp')
            if os.path.isfile(dcm_path):
                try:
                    log.info('reading %s' % dcm_path)
                    dcm = dicom.read_file(dcm_path)
                    break
                except:
                    pass
            else:
                log.warning('%s does not exist!' % dcm_path)
    else:
        log.info('Not a zip. Attempting to read %s directly' % os.path.basename(zip_file_path))
        dcm = dicom.read_file(zip_file_path)


    if not dcm:
        log.warning('dcm is empty!!!')
        os.sys.exit(1)

    # Build metadata
    metadata = {}

    # Session metadata
    metadata['session'] = {}
    session_timestamp, acquisition_timestamp = get_timestamp(dcm, timezone);
    if session_timestamp:
        metadata['session']['timestamp'] = session_timestamp
    if hasattr(dcm, 'OperatorsName') and dcm.get('OperatorsName'):
        metadata['session']['operator'] = dcm.get('OperatorsName')
    session_label = get_session_label(dcm)
    if session_label:
        metadata['session']['label'] = session_label

    # Subject Metadata
    metadata['session']['subject'] = {}
    if hasattr(dcm, 'PatientSex') and get_sex_string(dcm.get('PatientSex')):
        metadata['session']['subject']['sex'] = get_sex_string(dcm.get('PatientSex'))
    if hasattr(dcm, 'PatientAge') and dcm.get('PatientAge'):
        try:
            age = parse_patient_age(dcm.get('PatientAge'))
            if age:
                metadata['session']['subject']['age'] = int(age)
        except:
            pass
    if hasattr(dcm, 'PatientName') and dcm.get('PatientName').given_name:
        # If the first name or last name field has a space-separated string, and one or the other field is not
        # present, then we assume that the operator put both first and last names in that one field. We then
        # parse that field to populate first and last name.
        metadata['session']['subject']['firstname'] = dcm.get('PatientName').given_name
        if not dcm.get('PatientName').family_name:
            name = dcm.get('PatientName').given_name.split(' ')
            if len(name) == 2:
                first = name[0]
                last = name[1]
                metadata['session']['subject']['lastname'] = last
                metadata['session']['subject']['firstname'] = first
    if hasattr(dcm, 'PatientName') and dcm.get('PatientName').family_name:
        metadata['session']['subject']['lastname'] = dcm.get('PatientName').family_name
        if not dcm.get('PatientName').given_name:
            name = dcm.get('PatientName').family_name.split(' ')
            if len(name) == 2:
                first = name[0]
                last = name[1]
                metadata['session']['subject']['lastname'] = last
                metadata['session']['subject']['firstname'] = first

    # Acquisition
    metadata['acquisition'] = {}
    if hasattr(dcm, 'Modality') and dcm.get('Modality'):
        metadata['acquisition']['instrument'] = dcm.get('Modality')

    if hasattr(dcm, 'SeriesDescription') and dcm.get('SeriesDescription'):
        metadata['acquisition']['label'] = dcm.get('SeriesDescription')
        metadata['acquisition']['measurement'] = measurement_from_label.infer_measurement(dcm.get('SeriesDescription'))

    if not metadata['acquisition']['measurement'] or metadata['acquisition']['measurement'] == 'unknown':
        if dcm.get('Modality'):
            metadata['acquisition']['measurement'] = dcm.get('Modality')
        else:
            metadata['acquisition']['measurement'] = 'unknown'

    # If no pixel data present, make measurement "non-image"
    if not hasattr(dcm, 'PixelData'):
        metadata['acquisition']['measurement'] = 'non-image'

    if acquisition_timestamp:
        metadata['acquisition']['timestamp'] = acquisition_timestamp

    # Acquisition metadata from dicom header
    metadata['acquisition']['metadata'] = get_dicom_header(dcm)
    if dcm.Manufacturer == 'SIEMENS':
        csa_header = get_csa_header(dcm)
        if csa_header:
            metadata['acquisition']['metadata']['CSAHeader'] = csa_header

    # Write out the metadata to file (.metadata.json)
    metafile_outname = os.path.join(os.path.dirname(outbase),'.metadata.json')
    with open(metafile_outname, 'w') as metafile:
        json.dump(metadata, metafile)

    # Show the metadata
    pprint(metadata)

    return metafile_outname


if __name__ == '__main__':
    """
    Generate session, subject, and acquisition metatada by parsing the dicom header, using pydicom.
    """
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('dcmzip', help='path to dicom zip')
    ap.add_argument('outbase', nargs='?', help='outfile name prefix')
    ap.add_argument('--log_level', help='logging level', default='info')
    args = ap.parse_args()

    log.setLevel(getattr(logging, args.log_level.upper()))
    logging.getLogger('sctran.data').setLevel(logging.INFO)
    log.info('start: %s' % datetime.datetime.utcnow())

    args.timezone = validate_timezone(tzlocal.get_localzone())

    metadatafile = dicom_classify(args.dcmzip, args.outbase, args.timezone)

    if os.path.exists(metadatafile):
        log.info('generated %s' % metadatafile)
    else:
        log.info('failure! %s was not generated!' % metadatafile)

    log.info('stop: %s' % datetime.datetime.utcnow())
