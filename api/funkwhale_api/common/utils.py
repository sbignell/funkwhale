from django.utils.deconstruct import deconstructible

import os
import shutil
import uuid

from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from django.db import transaction


def rename_file(instance, field_name, new_name, allow_missing_file=False):
    field = getattr(instance, field_name)
    current_name, extension = os.path.splitext(field.name)

    new_name_with_extension = "{}{}".format(new_name, extension)
    try:
        shutil.move(field.path, new_name_with_extension)
    except FileNotFoundError:
        if not allow_missing_file:
            raise
        print("Skipped missing file", field.path)
    initial_path = os.path.dirname(field.name)
    field.name = os.path.join(initial_path, new_name_with_extension)
    instance.save()
    return new_name_with_extension


def on_commit(f, *args, **kwargs):
    return transaction.on_commit(lambda: f(*args, **kwargs))


def set_query_parameter(url, **kwargs):
    """Given a URL, set or replace a query parameter and return the
    modified URL.

    >>> set_query_parameter('http://example.com?foo=bar&biz=baz', 'foo', 'stuff')
    'http://example.com?foo=stuff&biz=baz'
    """
    scheme, netloc, path, query_string, fragment = urlsplit(url)
    query_params = parse_qs(query_string)

    for param_name, param_value in kwargs.items():
        query_params[param_name] = [param_value]
    new_query_string = urlencode(query_params, doseq=True)

    return urlunsplit((scheme, netloc, path, new_query_string, fragment))


@deconstructible
class ChunkedPath(object):
    def __init__(self, root, preserve_file_name=True):
        self.root = root
        self.preserve_file_name = preserve_file_name

    def __call__(self, instance, filename):
        uid = str(uuid.uuid4())
        chunk_size = 2
        chunks = [uid[i : i + chunk_size] for i in range(0, len(uid), chunk_size)]
        if self.preserve_file_name:
            parts = chunks[:3] + [filename]
        else:
            ext = os.path.splitext(filename)[1][1:].lower()
            new_filename = "".join(chunks[3:]) + ".{}".format(ext)
            parts = chunks[:3] + [new_filename]
        return os.path.join(self.root, *parts)


def chunk_queryset(source_qs, chunk_size):
    """
    From https://github.com/peopledoc/django-chunkator/blob/master/chunkator/__init__.py
    """
    pk = None
    # In django 1.9, _fields is always present and `None` if 'values()' is used
    # In Django 1.8 and below, _fields will only be present if using `values()`
    has_fields = hasattr(source_qs, "_fields") and source_qs._fields
    if has_fields:
        if "pk" not in source_qs._fields:
            raise ValueError("The values() call must include the `pk` field")

    field = source_qs.model._meta.pk
    # set the correct field name:
    # for ForeignKeys, we want to use `model_id` field, and not `model`,
    # to bypass default ordering on related model
    order_by_field = field.attname

    source_qs = source_qs.order_by(order_by_field)
    queryset = source_qs
    while True:
        if pk:
            queryset = source_qs.filter(pk__gt=pk)
        page = queryset[:chunk_size]
        page = list(page)
        nb_items = len(page)

        if nb_items == 0:
            return

        last_item = page[-1]
        # source_qs._fields exists *and* is not none when using "values()"
        if has_fields:
            pk = last_item["pk"]
        else:
            pk = last_item.pk

        yield page

        if nb_items < chunk_size:
            return
