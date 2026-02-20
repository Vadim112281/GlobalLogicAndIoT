from marshmallow import Schema, fields

class GpsSchema(Schema):
    longitude = fields.Number(required=True)
    latitude = fields.Number(required=True)