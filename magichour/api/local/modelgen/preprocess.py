"""
This module contains functions for the initial preprocessing of log files. The functions here are responsible
for reading in data and converting them into LogLine named tuples. (see named tuple definition in
magichour.api.local.util.namedtuples). Transforms named tuples represent a preprocessing step that .

TODO: Add the ability to write custom preprocessing functions other than just transforms.
"""

import gzip
import re
import json
import uuid

from magichour.api.local.util.log import get_logger
from magichour.api.local.util.namedtuples import DistributedLogLine, DistributedTransformLine

logger = get_logger(__name__)


def _read_lines(file_path):
    fp = gzip.open(
        file_path,
        'rb') if file_path.lower().endswith('.gz') else open(
        file_path,
        'r')
    for line in fp:
        yield line
    fp.close()


def read_log_file(
        file_path,
        ts_start_index,
        ts_end_index,
        ts_format=None,
        skip_num_chars=0,
        **kwargs):
    """
    Function to create LogLine named tuples from an input log file. Output from this function and get_transforms() is
    meant to be fed into get_transformed_lines() in order to apply the Transforms to the created LogLines. This
    function can be used by itself if you don't want to apply any Transforms, but keep in mind that writing and
    applying custom Transforms will assist the templating process.

    We make no underlying assumptions about the log file format other than that there is a timestamp associated with
    each line. The rest of each line is considered associated text.

    This function is a generator yielding LogLines. If you require a full list of LogLines then you will need
    to iterate through the generator.

    Unless there is an exception, the file is closed internally to the function.

    Args:
        file_path: path to log file. Open using gzip if file_path ends with .gz
        ts_start_index: starting index for parsing timestamp
        ts_end_index: end index for parsing timestamp
        ts_format: optional datetime format to pass to datetime.datetime.strptime to parse timestamp. If not
            specified, then the entire timestamp is parsed as a float.
        skip_num_chars: optional number of characters to skip parsing at the beginning of each line (Default = 0)

    Returns:
        a generator yielding LogLine objects created from each line in file_path
    """
    for line in _read_lines(file_path):
        line = line[skip_num_chars:]
        # Strip out timestamp and use ts_format to create time object.
        ts_str = line[ts_start_index:ts_end_index].strip()
        if ts_format:
            ts = time.mktime(
                datetime.datetime.strptime(
                    ts_str, ts_format).timetuple())
        else:
            ts = float(ts_str)
        text = line[:ts_start_index].join(line[ts_end_index:]).strip()
        yield DistributedLogLine(
            # id=str(uuid.uuid4()),
            ts=ts,
            text=text,
            processed=text,
            proc_dict=None,
            template=None,
            templateId=None,
            template_dict=None,
        )
        # yield LogLine(str(uuid.uuid4()), ts, text, None, None, None)


def read_auditd_file(file_path, **kwargs):
    for line in _read_lines(file_path):
        ts = float(re.search(r'audit\(([0-9]+\.[0-9]+)', line).group(1))
        yield DistributedLogLine(
            # id=str(uuid.uuid4()),
            ts=ts,
            text=line.rstrip(),
            processed=line.rstrip(),
            proc_dict=None,
            template=None,
            templateId=None,
            template_dict=None,
        )
        #LogLine(str(uuid.uuid4()), ts, line.rstrip(), None, None, None)


#####


def get_transforms(transforms_file):
    """
    Reads transforms from a file and returns a list of Transform named tuples. The output is meant to be fed into
    get_transformed_lines(). A Transform is a named tuple that represents a pattern to replace in a log line.
    The pattern is replaced by a standard tuple specified in the Transform file.

    The named tuple definition for Transform is:
    Transform = namedtuple('Transform', ['id', 'type', 'name', 'transform', 'compiled'])

    Args:
        file_path: a path to a transforms file. See documentation for proper format for the transforms file.

    Returns:
        transforms: list of Transform named tuples
    """
    transforms = []
    with open(transforms_file, 'r') as fp:
        for line in fp:
            line = line.strip()
            if len(line) == 0 or line[0] == '#':
                continue
            t_id, t_type, t_name, t_transform = line.split(',', 3)
            #transform = Transform(t_id, t_type, t_name, r''+t_transform, re.compile(r''+t_transform))
            transform = DistributedTransformLine(
                t_id,
                t_type,
                t_name,
                r'' +
                t_transform,
                re.compile(
                    r'' +
                    t_transform))
            transforms.append(transform)
    return transforms


def transform_lines(lines, transforms):
    """
    Function to return transformed LogLine named tuples by applying the specified Transforms on original
    LogLines (as generated by get_lines()). Note that writing and applying custom Transforms will assist the
    templating process and produce higher quality templates.

    For Transform.type==REPLACE operations:
        The Transform.transform regex must contain at least one capture group, which is saved and replaced with
        the Transform.name.

    This function is a generator yielding LogLines. If you require a full list of LogLines then you will need
    to iterate through the generator.

    See the comment in the function as to where to add additional transform types.

    Args:
        lines: iterable of LogLines named tuples.
        transforms: iterable of Transform named tuples.

    Returns:
        a generator yielding LogLine objects
    """
    for logline in lines:
        replaceDict = {}
        transformed = logline.text
        for transform in transforms:
            if transform.type == 'REPLACE':
                # save first capture group of each match
                matches = [m for m in transform.compiled.finditer(transformed)]
                if matches:
                    replaceDict[transform.name] = [m.group(1) for m in matches]
                    for m in reversed(matches):
                        # replace first capture group of each match with
                        # transform.name; reverse order to keep match start/end
                        # aligned
                        transformed = transformed[
                            :m.start(1)] + transform.name + transformed[m.end(1):]
            # elif transform.type == 'EXAMPLE':
                # Handle other transform types here.
                # do stuff
            else:
                # catch misspelled transform types
                raise NotImplementedError(
                    '%s Transform not implemented' %
                    transform.type)

        yield DistributedLogLine(
            # id=logline.id,
            ts=logline.ts,
            text=logline.text,
            processed=transformed,
            proc_dict=replaceDict,
            template=None,
            templateId=None,
            template_dict=None,
        )
        # yield LogLine(str(uuid.uuid4()), logline.ts, transformed, None,
        # replaceDict, None)


def log_cardinality(
        input_iterable,
        get_item=None,
        item_key=None,
        item_title='Item',
        verbose=False):
    """
    Diagnostic function to compute cardinality of items contained within input_iterable.  Computes number of unique items.

    Args:
        input_iterable: iterable containing items to count;
                            for input in input_iterable:
        get_item: accessor to get item from input; e.g. operator.attrgetter('attr') -> input.attr
                      default = input
        item_key: sort key to call on get_item; default = None (use get_item as key)
        verbose: True = print evaluated results (default=False)

    Returns:
        (countInput, countUniqueInput, percentUniqueInput, uniqInput)
            countInput: count of input_iterable
            countUniqueInput: count of unique input_iterable
            percentUniqueInput: 100.0 * countUniqueInput / countInput
            uniqInput: dictionary[uniq_line_text] = number of occurrences of uniq_line
    """
    from collections import defaultdict
    from pprint import pformat

    if not get_item:
        get_item = lambda x: x
    if not item_key:
        item_key = lambda x: x

    uniqInput = {}
    countInput = 0

    for element in input_iterable:
        item = get_item(element)
        item_str = str(item)
        sort_key, count = uniqInput.get(item_str, (item_key(item), 0))
        uniqInput[item_str] = (sort_key, count + 1)
        countInput += 1
    countUniqueInput = len(uniqInput)
    percentUniqueInput = 100.0 * countUniqueInput / countInput if countInput else 0
    logger.info(
        "%s cardinality: (%d / %d) = %f%%; (uniqueInput / totalInput) = %%uniqueInput" %
        (item_title, countUniqueInput, countInput, percentUniqueInput))
    if verbose:
        sorted_uniqInput = ((v[1], k) for k, v in sorted(
            uniqInput.iteritems(), key=lambda k_v: k_v[1]))
        e = []
        for occurrences, text in sorted_uniqInput:
            e.append("%10d: %s" % (occurrences, text))
        logger.info("%ss: %d" % (item_title, countUniqueInput))
        logger.info("\n" + pformat(e))
    return (countInput, countUniqueInput, percentUniqueInput, uniqInput)
