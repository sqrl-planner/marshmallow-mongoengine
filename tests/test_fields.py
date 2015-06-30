# -*- coding: utf-8 -*-
from __future__ import absolute_import
import datetime as dt
import decimal
from datetime import datetime

import mongoengine as me

from marshmallow import validate, Schema

import pytest
from marshmallow_mongoengine import (fields, fields_for_model, ModelSchema,
                                     ModelConverter, convert_field, field_for)


TEST_DB = 'marshmallow_mongoengine-test'
db = me.connect(TEST_DB)


class BaseTest(object):
    @classmethod
    def setup_method(self, method):
        # Reset database from previous test run
        db.drop_database(TEST_DB)


def contains_validator(field, v_type):
    for v in field.validators:
        if isinstance(v, v_type):
            return v
    return False


class TestFields(BaseTest):

    def test_FileField(self):
        class File(me.Document):
            name = me.StringField(primary_key=True)
            file = me.FileField()
        class FileSchema(ModelSchema):
            class Meta:
                model = File
        doc = File(name='test_file')
        data = b'1234567890' * 10
        doc.file.put(data, content_type='application/octet-stream')
        dump = FileSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'name': 'test_file'}
        # Should not be able to load the file
        load = FileSchema().load({'name': 'bad_load', 'file': b'12345'})
        assert not load.data.file

    def test_ListField(self):
        class Doc(me.Document):
            list = me.ListField(me.StringField())
        fields_ = fields_for_model(Doc)
        assert type(fields_['list']) is fields.List
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        list_ = ['A', 'B', 'C']
        doc = Doc(list=list_)
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'list': list_}
        load = DocSchema().load(dump.data)
        assert not load.errors
        assert load.data.list == list_

    def test_DictField(self):
        class Doc(me.Document):
            data = me.DictField()
        fields_ = fields_for_model(Doc)
        assert type(fields_['data']) is fields.Raw
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        data = {
            'int_1': 1,
            'nested_2': {
                'sub_int_1': 42,
                'sub_list_2': []
            },
            'list_3': ['a', 'b', 'c']
        }
        doc = Doc(data=data)
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'data': data}
        load = DocSchema().load(dump.data)
        assert not load.errors
        assert load.data.data == data

    def test_DynamicField(self):
        class Doc(me.Document):
            dynamic = me.DynamicField()
        fields_ = fields_for_model(Doc)
        assert type(fields_['dynamic']) is fields.Raw
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        data = {
            'int_1': 1,
            'nested_2': {
                'sub_int_1': 42,
                'sub_list_2': []
            },
            'list_3': ['a', 'b', 'c']
        }
        doc = Doc(dynamic=data)
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'dynamic': data}
        load = DocSchema().load(dump.data)
        assert not load.errors
        assert load.data.dynamic == data

    def test_GenericReferenceField(self):
        class Doc(me.Document):
            id = me.StringField(primary_key=True, default='main')
            generic = me.GenericReferenceField()
        class SubDocA(me.Document):
            field_a = me.StringField(primary_key=True, default='doc_a_pk')
        class SubDocB(me.Document):
            field_b = me.IntField(primary_key=True, default=42)
        fields_ = fields_for_model(Doc)
        assert type(fields_['generic']) is fields.GenericReference
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        sub_doc_a = SubDocA().save()
        sub_doc_b = SubDocB().save()
        doc = Doc(generic=sub_doc_a)
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'generic': 'doc_a_pk', 'id': 'main'}
        doc.generic = sub_doc_b
        doc.save()
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'generic': 42, 'id': 'main'}
        # TODO: test load ?

    def test_GenericEmbeddedDocumentField(self):
        class Doc(me.Document):
            id = me.StringField(primary_key=True, default='main')
            embedded = me.GenericEmbeddedDocumentField()
        class EmbeddedA(me.EmbeddedDocument):
            field_a = me.StringField(default='field_a_value')
        class EmbeddedB(me.EmbeddedDocument):
            field_b = me.IntField(default=42)
        fields_ = fields_for_model(Doc)
        assert type(fields_['embedded']) is fields.GenericEmbeddedDocument
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        doc = Doc(embedded=EmbeddedA())
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'embedded': {'field_a': 'field_a_value'}, 'id': 'main'}
        doc.embedded = EmbeddedB()
        doc.save()
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'embedded': {'field_b': 42}, 'id': 'main'}
        # TODO: test load ?

    def test_MapField(self):
        class MappedDoc(me.EmbeddedDocument):
            field = me.StringField()
        class Doc(me.Document):
            id = me.IntField(primary_key=True, default=1)
            map = me.MapField(me.EmbeddedDocumentField(MappedDoc))
        fields_ = fields_for_model(Doc)
        assert type(fields_['map']) is fields.Map
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        doc = Doc(map={'a': MappedDoc(field='A'), 'b': MappedDoc(field='B')}).save()
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'map': {'a': {'field': 'A'}, 'b': {'field': 'B'}}, 'id': 1}
        # Try the load
        load = DocSchema().load(dump.data)
        assert not load.errors
        assert load.data.map == doc.map

    def test_ReferenceField(self):
        class ReferenceDoc(me.Document):
            field = me.IntField(primary_key=True, default=42)
        class Doc(me.Document):
            id = me.StringField(primary_key=True, default='main')
            ref = me.ReferenceField(ReferenceDoc)
        fields_ = fields_for_model(Doc)
        assert type(fields_['ref']) is fields.Reference
        class DocSchema(ModelSchema):
            class Meta:
                model = Doc
        ref_doc = ReferenceDoc().save()
        doc = Doc(ref=ref_doc)
        dump = DocSchema().dump(doc)
        assert not dump.errors
        assert dump.data == {'ref': 42, 'id': 'main'}
        # Try the same with reference document type passed as string
        class DocSchemaRefAsString(Schema):
            id = fields.String()
            ref = fields.Reference('ReferenceDoc')
        dump = DocSchemaRefAsString().dump(doc)
        assert not dump.errors
        assert dump.data == {'ref': 42, 'id': 'main'}
        load = DocSchemaRefAsString().load(dump.data)
        assert not load.errors
        assert type(load.data['ref']) == ReferenceDoc