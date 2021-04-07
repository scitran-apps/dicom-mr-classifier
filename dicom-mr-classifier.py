#!/usr/bin/env python

import os
import re
import json
import pytz
import pydicom
import string
import tzlocal
import logging
import zipfile
import datetime
import classification_from_label
from fnmatch import fnmatch
from pprint import pprint

logging.basicConfig()
log = logging.getLogger("dicom-mr-classifier")

DEFAULT_TME = '120000.00'


def get_session_label(dcm):
    """
    Switch on manufacturer and either pull out the StudyID or the StudyInstanceUID
    """
    session_label = ""
    if (
        dcm.get("Manufacturer")
        and (
            dcm.get("Manufacturer").find("GE") != -1
            or dcm.get("Manufacturer").find("Philips") != -1
        )
        and dcm.get("StudyID")
    ):
        session_label = dcm.get("StudyID")
    else:
        session_label = dcm.get("StudyInstanceUID")

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
    if age == "None" or not age:
        return None

    conversion = {  # conversion to days
        "Y": 365.25,
        "M": 30,
        "W": 7,
        "D": 1,
    }
    scale = age[-1:]
    value = age[:-1]
    if scale not in conversion.keys():
        # Assume years
        scale = "Y"
        value = age

    age_in_seconds = datetime.timedelta(
        int(value) * conversion.get(scale)
    ).total_seconds()

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
        try:
            return timezone.localize(
                datetime.datetime.strptime(date + time[:6], "%Y%m%d%H%M%S"), timezone
            )
        except:
            log.warning("Failed to create timestamp!")
            log.info(date)
            log.info(time)
            log.info(timezone)
            return None
    return None


def get_timestamp(dcm, timezone):
    """
    Parse Study Date and Time, return acquisition and session timestamps.

    For study date/time Dicom tag used by order of priority goes like a:
        - StudyDate/StudyTime
        - SeriesDate/SeriesTime
        - AcquisitionDate/AcquisitionTime
        - AcquisitionDateTime
        - StudyDate and Time defaults to DEFAULT_TME
        - SeriesDates and Time defaults to DEFAULT_TME
        - AcquisitionDate and Time defaults to DEFAULT_TME

    For acquisition date/time Dicom tag used by order of priority goes like a:
        - SeriesDate/SeriesTime
        - AcquisitionDate/AcquisitionTime
        - AcquisitionDateTime
        - ContentDate/ContentTime
        - StudyDate/StudyTime
        - SeriesDate and Time defaults to DEFAULT_TME
        - AcquisitionDate and Time defaults to DEFAULT_TME
        - StudyDate and Time defaults to DEFAULT_TME
    """
    # Study Date and Time, with precedence as below
    if getattr(dcm, 'StudyDate', None) and getattr(dcm, 'StudyTime', None):
        study_date = dcm.StudyDate
        study_time = dcm.StudyTime
    elif getattr(dcm, 'SeriesDate', None) and getattr(dcm, 'SeriesTime', None):
        study_date = dcm.SeriesDate
        study_time = dcm.SeriesTime
    elif getattr(dcm, 'AcquisitionDate', None) and getattr(dcm, 'AcquisitionTime', None):
        study_date = dcm.AcquisitionDate
        study_time = dcm.AcquisitionTime
    elif getattr(dcm, 'AcquisitionDateTime', None):
        study_date = dcm.AcquisitionDateTime[0:8]
        study_time = dcm.AcquisitionDateTime[8:]
    # If only Dates are available setting time to 00:00
    elif getattr(dcm, 'StudyDate', None):
        study_date = dcm.StudyDate
        study_time = DEFAULT_TME
    elif getattr(dcm, 'SeriesDate', None):
        study_date = dcm.SeriesDate
        study_time = DEFAULT_TME
    elif getattr(dcm, 'AcquisitionDate', None):
        study_date = dcm.AcquisitionDate
        study_time = DEFAULT_TME
    else:
        study_date = None
        study_time = None

    # Acquisition Date and Time, with precedence as below
    if getattr(dcm, 'SeriesDate', None) and getattr(dcm, 'SeriesTime', None):
        acquisition_date = dcm.SeriesDate
        acquisition_time = dcm.SeriesTime
    elif getattr(dcm, 'AcquisitionDate', None) and getattr(dcm, 'AcquisitionTime', None):
        acquisition_date = dcm.AcquisitionDate
        acquisition_time = dcm.AcquisitionTime
    elif getattr(dcm, 'AcquisitionDateTime', None):
        acquisition_date = dcm.AcquisitionDateTime[0:8]
        acquisition_time = dcm.AcquisitionDateTime[8:]
    # The following allows the timestamps to be set for ScreenSaves
    elif getattr(dcm, 'ContentDate', None) and getattr(dcm, 'ContentTime', None):
        acquisition_date = dcm.ContentDate
        acquisition_time = dcm.ContentTime
    # Looking deeper if nothing found so far
    elif getattr(dcm, 'StudyDate', None) and getattr(dcm, 'StudyTime', None):
        acquisition_date = dcm.StudyDate
        acquisition_time = dcm.StudyTime
    # If only Dates are available setting time to 00:00
    elif getattr(dcm, 'SeriesDate', None):
        acquisition_date = dcm.SeriesDate
        acquisition_time = DEFAULT_TME
    elif getattr(dcm, 'AcquisitionDate', None):
        acquisition_date = dcm.AcquisitionDate
        acquisition_time = DEFAULT_TME
    elif getattr(dcm, 'StudyDate', None):
        acquisition_date = dcm.StudyDate
        acquisition_time = DEFAULT_TME

    else:
        acquisition_date = None
        acquisition_time = None

    session_timestamp = timestamp(study_date, study_time, timezone)
    acquisition_timestamp = timestamp(acquisition_date, acquisition_time, timezone)

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
    if sex_str == "M":
        sex = "male"
    elif sex_str == "F":
        sex = "female"
    else:
        sex = ""
    return sex


def assign_type(s):
    """
    Sets the type of a given input.
    """
    if (
        isinstance(s, pydicom.valuerep.PersonName)
    ):
        return format_string(s)
    if type(s) == list or type(s) == pydicom.multival.MultiValue:
        try:
            return [int(x) if type(x) == int else float(x) for x in s]
        except ValueError:
            return [format_string(x) for x in s if len(x) > 0]
    elif type(s) == float or type(s) == int:
        return s
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
    formatted = re.sub(
        r"[^\x00-\x7f]", r"", str(in_string)
    )  # Remove non-ascii characters
    formatted = "".join(filter(lambda x: x in string.printable, formatted))
    if len(formatted) == 1 and formatted == "?":
        formatted = None
    return formatted  # .encode('utf-8').strip()


def get_seq_data(sequence, ignore_keys):
    seq_dict = {}
    for seq in sequence:
        for s_key in seq.dir():
            s_val = getattr(seq, s_key, "")
            if type(s_val) is pydicom.uid.UID or s_key in ignore_keys:
                continue

            if type(s_val) == pydicom.sequence.Sequence:
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
    exclude_tags = [
        "[Unknown]",
        "PixelData",
        "Pixel Data",
        "[User defined data]",
        "[Protocol Data Block (compressed)]",
        "[Histogram tables]",
        "[Unique image iden]",
    ]
    tags = dcm.dir()
    for tag in tags:
        try:
            if (tag not in exclude_tags) and (
                type(dcm.get(tag)) != pydicom.sequence.Sequence
            ):
                value = dcm.get(tag)
                if value or value == 0:  # Some values are zero
                    # Put the value in the header
                    if (
                        type(value) == str and len(value) < 10240
                    ):  # Max dicom field length
                        header[tag] = format_string(value)
                    else:
                        header[tag] = assign_type(value)
                else:
                    log.debug("No value found for tag: " + tag)

            if type(dcm.get(tag)) == pydicom.sequence.Sequence:
                seq_data = get_seq_data(dcm.get(tag), exclude_tags)
                # Check that the sequence is not empty
                if seq_data:
                    header[tag] = seq_data
        except:
            log.debug("Failed to get " + tag)
            pass
    return header


def get_csa_header(dcm):
    import pydicom
    import nibabel.nicom.dicomwrappers

    exclude_tags = ["PhoenixZIP", "SrMsgBuffer"]
    header = {}
    try:
        raw_csa_header = nibabel.nicom.dicomwrappers.SiemensWrapper(dcm).csa_header
        tags = raw_csa_header["tags"]
    except:
        log.warning("Failed to parse csa header!")
        return header

    for tag in tags:
        if not raw_csa_header["tags"][tag]["items"] or tag in exclude_tags:
            log.debug("Skipping : %s" % tag)
            pass
        else:
            value = raw_csa_header["tags"][tag]["items"]
            if len(value) == 1:
                value = value[0]
                if type(value) == str and (len(value) > 0 and len(value) < 1024):
                    header[format_string(tag)] = format_string(value)
                else:
                    header[format_string(tag)] = assign_type(value)
            else:
                header[format_string(tag)] = assign_type(value)

    return header


def get_classification_from_string(value):
    result = {}

    parts = re.split(r"\s*,\s*", value)
    last_key = None
    for part in parts:
        key_value = re.split(r"\s*:\s*", part)

        if len(key_value) == 2:
            last_key = key = key_value[0]
            value = key_value[1]
        else:
            if last_key:
                key = last_key
            else:
                log.warn("Unknown classification format: {0}".format(part))
                key = "Custom"
            value = part

        if key not in result:
            result[key] = []

        result[key].append(value)

    return result


def get_custom_classification(label, config=None):
    if config is None:
        return None

    # Check custom classifiers
    classifications = config["inputs"].get("classifications", {}).get("value", {})
    if not classifications:
        log.debug("No custom classifications found in config")
        return None

    if not isinstance(classifications, dict):
        log.warning("classifications must be an object!")
        return None

    for k in classifications.keys():
        val = classifications[k]

        if not isinstance(val, basestring):
            log.warn("Expected string value for classification key %s", k)
            continue

        if len(k) > 2 and k[0] == "/" and k[-1] == "/":
            # Regex
            try:
                if re.search(k[1:-1], label, re.I):
                    log.debug("Matched custom classification for key: %s", k)
                    return get_classification_from_string(val)
            except re.error:
                log.exception("Invalid regular expression: %s", k)
        elif fnmatch(label.lower(), k.lower()):
            log.debug("Matched custom classification for key: %s", k)
            return get_classification_from_string(val)

    return None


def dicom_classify(zip_file_path, outbase, timezone, config=None):
    """
    Extracts metadata from dicom file header within a zip file and writes to .metadata.json.
    """
    import pydicom

    # Parse config for options
    if config:
        config_force = config["config"].get("force")
        if config_force:
            log.warning("Attempting to force DICOM read. Input DICOM may not be valid.")
    else:
        config_force = False

    # Check for input file path
    if not os.path.exists(zip_file_path):
        log.debug("could not find %s" % zip_file_path)
        log.debug("checking input directory ...")
        if os.path.exists(os.path.join("/input", zip_file_path)):
            zip_file_path = os.path.join("/input", zip_file_path)
            log.debug("found %s" % zip_file_path)

    if not outbase:
        outbase = "/flywheel/v0/output"
        log.info("setting outbase to %s" % outbase)

    # Extract the last file in the zip to /tmp/ and read it
    dcm = []
    if zipfile.is_zipfile(zip_file_path):
        zip = zipfile.ZipFile(zip_file_path)
        num_files = len(zip.namelist())
        for n in range((num_files - 1), -1, -1):
            dcm_path = zip.extract(zip.namelist()[n], "/tmp")
            if os.path.isfile(dcm_path):
                try:
                    log.info("reading %s" % dcm_path)
                    dcm = pydicom.dcmread(dcm_path, force=config_force)
                    # Here we check for the Raw Data Storage SOP Class, if there
                    # are other DICOM files in the zip then we read the next one,
                    # if this is the only class of DICOM in the file, we accept
                    # our fate and move on.
                    if (
                        dcm.get("SOPClassUID") == "Raw Data Storage"
                        and n != range((num_files - 1), -1, -1)[-1]
                    ):
                        continue
                    else:
                        break
                except:
                    pass
            else:
                log.warning("%s does not exist!" % dcm_path)
    else:
        log.info(
            "Not a zip. Attempting to read %s directly"
            % os.path.basename(zip_file_path)
        )
        dcm = pydicom.dcmread(zip_file_path)

    if not dcm:
        log.warning(
            'DICOM could not be read! Is this a valid DICOM file? To force parsing the file, run again setting "force" configuration option to "true"'
        )
        os.sys.exit(1)

    # Build metadata
    metadata = {}

    # Session metadata
    metadata["session"] = {}
    session_timestamp, acquisition_timestamp = get_timestamp(dcm, timezone)
    if session_timestamp:
        metadata["session"]["timestamp"] = session_timestamp
    if hasattr(dcm, "OperatorsName") and dcm.get("OperatorsName"):
        metadata["session"]["operator"] = format_string(dcm.get("OperatorsName"))
    session_label = get_session_label(dcm)
    if session_label:
        metadata["session"]["label"] = session_label

    if hasattr(dcm, "PatientWeight") and dcm.get("PatientWeight"):
        metadata["session"]["weight"] = assign_type(dcm.get("PatientWeight"))

    # Subject Metadata
    metadata["session"]["subject"] = {}
    if hasattr(dcm, "PatientSex") and get_sex_string(dcm.get("PatientSex")):
        metadata["session"]["subject"]["sex"] = get_sex_string(dcm.get("PatientSex"))
    if hasattr(dcm, "PatientAge") and dcm.get("PatientAge"):
        try:
            age = parse_patient_age(dcm.get("PatientAge"))
            if age:
                metadata["session"]["age"] = int(age)
        except:
            pass
    if hasattr(dcm, "PatientName") and dcm.get("PatientName").given_name:
        # If the first name or last name field has a space-separated string, and one or the other field is not
        # present, then we assume that the operator put both first and last names in that one field. We then
        # parse that field to populate first and last name.
        metadata["session"]["subject"]["firstname"] = str(
            format_string(dcm.get("PatientName").given_name)
        )
        if not dcm.get("PatientName").family_name:
            name = format_string(dcm.get("PatientName").given_name.split(" "))
            if len(name) == 2:
                first = name[0]
                last = name[1]
                metadata["session"]["subject"]["lastname"] = str(last)
                metadata["session"]["subject"]["firstname"] = str(first)
    if hasattr(dcm, "PatientName") and dcm.get("PatientName").family_name:
        metadata["session"]["subject"]["lastname"] = str(
            format_string(dcm.get("PatientName").family_name)
        )
        if not dcm.get("PatientName").given_name:
            name = format_string(dcm.get("PatientName").family_name.split(" "))
            if len(name) == 2:
                first = name[0]
                last = name[1]
                metadata["session"]["subject"]["lastname"] = str(last)
                metadata["session"]["subject"]["firstname"] = str(first)

    # File classification
    dicom_file = {}
    dicom_file["name"] = os.path.basename(zip_file_path)
    dicom_file["modality"] = format_string(dcm.get("Modality", "MR") or "MR")
    if dcm.get('Modality'):
        dicom_file["modality"] = format_string(dcm.get("Modality"))
    else:
        log.warning('No modality found.')
        dicom_file["modality"] = None

    dicom_file["classification"] = {}

    # Acquisition metadata
    metadata["acquisition"] = {}
    if acquisition_timestamp:
        metadata["acquisition"]["timestamp"] = acquisition_timestamp

    if hasattr(dcm, "Modality") and dcm.get("Modality"):
        metadata["acquisition"]["instrument"] = format_string(dcm.get("Modality"))

    series_desc = format_string(dcm.get("SeriesDescription", ""))
    if series_desc:
        metadata["acquisition"]["label"] = series_desc
        classification = get_custom_classification(series_desc, config)
        log.info("Custom classification from config: %s", classification)
        if not classification:
            classification = classification_from_label.infer_classification(series_desc)
            log.info("Inferred classification from label: %s", classification)
        dicom_file["classification"] = classification

    # If no pixel data present, make classification intent "Non-Image"
    if not hasattr(dcm, "PixelData"):
        nonimage_intent = {"Intent": ["Non-Image"]}
        # If classification is a dict, update dict with intent
        if isinstance(dicom_file["classification"], dict):
            dicom_file["classification"].update(nonimage_intent)
        # Else classification is a list, assign dict with intent
        else:
            dicom_file["classification"] = nonimage_intent

    # File info from dicom header
    dicom_file["info"] = get_dicom_header(dcm)

    # Grab CSA header for Siemens data
    if dcm.get("Manufacturer") == "SIEMENS":
        csa_header = get_csa_header(dcm)
        if csa_header:
            dicom_file["info"]["CSAHeader"] = csa_header

    # Append the dicom_file to the files array
    metadata["acquisition"]["files"] = [dicom_file]

    # Write out the metadata to file (.metadata.json)
    metafile_outname = os.path.join(os.path.dirname(outbase), ".metadata.json")
    with open(metafile_outname, "w") as metafile:
        json.dump(metadata, metafile)

    # Show the metadata
    pprint(metadata)

    return metafile_outname


if __name__ == "__main__":
    """
    Generate session, subject, and acquisition metatada by parsing the dicom header, using pydicom.
    """
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("dcmzip", help="path to dicom zip")
    ap.add_argument("outbase", nargs="?", help="outfile name prefix")
    ap.add_argument("--log_level", help="logging level", default="info")
    ap.add_argument(
        "--config-file",
        default="/flywheel/v0/config.json",
        help="Configuration file with custom classifications in context",
    )
    args = ap.parse_args()

    log.setLevel(getattr(logging, args.log_level.upper()))
    logging.getLogger("sctran.data").setLevel(logging.INFO)
    log.info("start: %s" % datetime.datetime.utcnow())

    args.timezone = validate_timezone(tzlocal.get_localzone())

    # Load config from file
    if args.config_file and os.path.isfile(args.config_file):
        with open(args.config_file) as json_file:
            config = json.load(json_file)
    else:
        config = None

    metadatafile = dicom_classify(args.dcmzip, args.outbase, args.timezone, config)

    if os.path.exists(metadatafile):
        log.info("generated %s" % metadatafile)
    else:
        log.info("failure! %s was not generated!" % metadatafile)

    log.info("stop: %s" % datetime.datetime.utcnow())
