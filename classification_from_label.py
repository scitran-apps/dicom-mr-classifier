#!/usr/bin/env python
'''
Infer acquisition classification by parsing the description label.


Example DB usage:

    ## Update acquisition measurement in the DB
    labels=list(db.acquisitions.find({},['label']))

    labels_only = []
    for l in labels:
        labels_only.append(l['label'])

    unique_labels = set(labels_only)
    uls = list(unique_labels)

    for l in uls:
        measurement = infer_measurement(l)
        db.acquisitions.update_many({'label': l}, {'$set': {'measurement': measurement}})
'''

import re


# Anatomy, T1
def is_anatomy_t1(label):
    regexes = [
        re.compile('t1', re.IGNORECASE),
        re.compile('t1w', re.IGNORECASE),
        re.compile('(?=.*3d anat)(?![inplane])', re.IGNORECASE),
        re.compile('(?=.*3d)(?=.*bravo)(?![inplane])', re.IGNORECASE),
        re.compile('spgr', re.IGNORECASE),
        re.compile('tfl', re.IGNORECASE),
        re.compile('mprage', re.IGNORECASE),
        re.compile('(?=.*mm)(?=.*iso)', re.IGNORECASE),
        re.compile('(?=.*mp)(?=.*rage)', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)


# Anatomy, T2
def is_anatomy_t2(label):
    regexes = [
        re.compile('t2', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)


# Anatomy, Inplane
def is_anatomy_inplane(label):
    regexes = [
        re.compile('inplane', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)


# Anatomy, other
def is_anatomy(label):
    regexes = [
        re.compile('(?=.*IR)(?=.*EPI)', re.IGNORECASE),
        re.compile('flair', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)


# Diffusion
def is_diffusion(label):
    regexes = [
        re.compile('dti', re.IGNORECASE),
        re.compile('dwi', re.IGNORECASE),
        re.compile('diff_', re.IGNORECASE),
        re.compile('diffusion', re.IGNORECASE),
        re.compile('(?=.*diff)(?=.*dir)', re.IGNORECASE),
        re.compile('hardi', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Diffusion - Derived
def is_diffusion_derived(label):
    regexes = [
        re.compile('_ADC$', re.IGNORECASE),
        re.compile('_TRACEW$', re.IGNORECASE),
        re.compile('_ColFA$', re.IGNORECASE),
        re.compile('_FA$', re.IGNORECASE),
        re.compile('_EXP$', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Functional
def is_functional(label):
    regexes = [
        re.compile('functional', re.IGNORECASE),
        re.compile('fmri', re.IGNORECASE),
        re.compile('func', re.IGNORECASE),
        re.compile('bold', re.IGNORECASE),
        re.compile('resting', re.IGNORECASE),
        re.compile('(?=.*rest)(?=.*state)', re.IGNORECASE),
        # NON-STANDARD
        re.compile('(?=.*ret)(?=.*bars)', re.IGNORECASE),
        re.compile('(?=.*ret)(?=.*wedges)', re.IGNORECASE),
        re.compile('(?=.*ret)(?=.*rings)', re.IGNORECASE),
        re.compile('(?=.*ret)(?=.*check)', re.IGNORECASE),
        re.compile('go-no-go', re.IGNORECASE),
        re.compile('words', re.IGNORECASE),
        re.compile('checkers', re.IGNORECASE),
        re.compile('retinotopy', re.IGNORECASE),
        re.compile('faces', re.IGNORECASE),
        re.compile('rings', re.IGNORECASE),
        re.compile('wedges', re.IGNORECASE),
        re.compile('emoreg', re.IGNORECASE),
        re.compile('conscious', re.IGNORECASE),
        re.compile('^REST$'),
        re.compile('ep2d', re.IGNORECASE),
        re.compile('task', re.IGNORECASE),
        re.compile('rest', re.IGNORECASE),
        re.compile('fBIRN', re.IGNORECASE),
        re.compile('^Curiosity', re.IGNORECASE),
        re.compile('^DD_', re.IGNORECASE),
        re.compile('^Poke', re.IGNORECASE),
        re.compile('^Effort', re.IGNORECASE),
        re.compile('emotion|conflict', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Functional, Derived
def is_functional_derived(label):
    regexes = [
        re.compile('mocoseries', re.IGNORECASE),
        re.compile('GLM$', re.IGNORECASE),
        re.compile('t-map', re.IGNORECASE),
        re.compile('design', re.IGNORECASE),
        re.compile('StartFMRI', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Localizer
def is_localizer(label):
    regexes = [
        re.compile('localizer', re.IGNORECASE),
        re.compile('localiser', re.IGNORECASE),
        re.compile('survey', re.IGNORECASE),
        re.compile('loc\.', re.IGNORECASE),
        re.compile(r'\bscout\b', re.IGNORECASE),
        re.compile('(?=.*plane)(?=.*loc)', re.IGNORECASE),
        re.compile('(?=.*plane)(?=.*survey)', re.IGNORECASE),
        re.compile('3-plane', re.IGNORECASE),
        re.compile('^loc*', re.IGNORECASE),
        re.compile('Scout', re.IGNORECASE),
        re.compile('AdjGre', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Shim
def is_shim(label):
    regexes = [
        re.compile('(?=.*HO)(?=.*shim)', re.IGNORECASE),  # Contians 'ho' and 'shim'
        re.compile(r'\bHOS\b', re.IGNORECASE),
        re.compile('_HOS_', re.IGNORECASE),
        re.compile('.*shim', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Fieldmap
def is_fieldmap(label):
    regexes = [
        re.compile('(?=.*field)(?=.*map)', re.IGNORECASE),
        re.compile('(?=.*bias)(?=.*ch)', re.IGNORECASE),
        re.compile('field', re.IGNORECASE),
        re.compile('fmap', re.IGNORECASE),
        re.compile('topup', re.IGNORECASE),
        re.compile('DISTORTION', re.IGNORECASE),
        re.compile('se[-_][aprl]{2}$', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Calibration
def is_calibration(label):
    regexes = [
        re.compile('(?=.*asset)(?=.*cal)', re.IGNORECASE),
        re.compile('^asset$', re.IGNORECASE),
        re.compile('calibration', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Coil Survey
def is_coil_survey(label):
    regexes = [
        re.compile('(?=.*coil)(?=.*survey)', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Perfusion: Arterial Spin Labeling
def is_perfusion(label):
    regexes = [
        re.compile('asl', re.IGNORECASE),
        re.compile('(?=.*blood)(?=.*flow)', re.IGNORECASE),
        re.compile('(?=.*art)(?=.*spin)', re.IGNORECASE),
        re.compile('tof', re.IGNORECASE),
        re.compile('perfusion', re.IGNORECASE),
        re.compile('angio', re.IGNORECASE),
        ]
    return regex_search_label(regexes, label)


# Proton Density
def is_proton_density(label):
    regexes = [
        re.compile('^PD$'),
        re.compile('(?=.*proton)(?=.*density)', re.IGNORECASE),
        re.compile('pd_'),
        re.compile('_pd')
        ]
    return regex_search_label(regexes, label)


# Phase Map
def is_phase_map(label):
    regexes = [
        re.compile('(?=.*phase)(?=.*map)', re.IGNORECASE),
        re.compile('^phase$', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Screen Save / Screenshot
def is_screenshot(label):
    regexes = [
        re.compile('(?=.*screen)(?=.*save)', re.IGNORECASE),
        re.compile('.*screenshot', re.IGNORECASE),
        re.compile('.*screensave', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Utility:  Check a list of regexes for truthyness
def regex_search_label(regexes, label):
    if any(regex.search(label) for regex in regexes):
            return True
    else:
            return False


# Spectroscopy
def is_spectroscopy(label):
    regexes = [
        re.compile('mip', re.IGNORECASE),
        re.compile('mrs', re.IGNORECASE),
        re.compile('svs', re.IGNORECASE),
        re.compile('gaba', re.IGNORECASE),
        re.compile('csi', re.IGNORECASE),
        re.compile('nfl', re.IGNORECASE),
        re.compile('mega', re.IGNORECASE),
        re.compile('press', re.IGNORECASE),
        re.compile('spect', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)


# Call all functions to determine new label
def infer_classification(label):
    if not label:
        return {}
    else:
        classification = {}
        if is_anatomy_inplane(label):
            classification['Intent'] = ['Structural']
            classification['Measurement'] = ['T1']
            classification['Features'] = ['In-Plane']
        elif is_fieldmap(label):
            classification['Intent'] = ['Fieldmap']
            classification['Measurement'] = ['B0']
        elif is_diffusion_derived(label):
            classification['Intent'] = ['Structural']
            classification['Measurement'] = ['Diffusion']
            classification['Features'] = ['Derived']
        elif is_diffusion(label):
            classification['Intent'] = ['Structural']
            classification['Measurement'] = ['Diffusion']
        elif is_functional_derived(label):
            classification['Intent'] = ['Functional']
            classification['Features'] = ['Derived']
        elif is_functional(label):
            classification['Intent'] = ['Functional']
            classification['Measurement'] = ['T2*']
        elif is_anatomy_t1(label):
            classification['Intent'] = ['Structural']
            classification['Measurement'] = ['T1']
        elif is_anatomy_t2(label):
            classification['Intent'] = ['Structural']
            classification['Measurement'] = ['T2']
        elif is_anatomy(label):
            classification['Intent'] = ['Structural']
        elif is_localizer(label):
            classification['Intent'] = ['Localizer']
            classification['Measurement'] = ['T2']
        elif is_shim(label):
            classification['Intent'] = ['Shim']
        elif is_calibration(label):
            classification['Intent'] = ['Calibration']
        elif is_coil_survey(label):
            classification['Intent'] = ['Calibration']
            classification['Measurement'] = ['B1']
        elif is_proton_density(label):
            classification['Intent'] = ['Structural']
            classification['Measurement'] = ['PD']
        elif is_perfusion(label):
            classification['Measurement'] = ['Perfusion']
        elif is_spectroscopy(label):
            classification['Intent'] = ['Spectroscopy']
        elif is_phase_map(label):
            classification['Custom'] = ['Phase Map']
        elif is_screenshot(label):
            classification['Intent'] = ['Screenshot']
        else:
            print(label.strip('\n') + ' --->>>> unknown')

    return classification
