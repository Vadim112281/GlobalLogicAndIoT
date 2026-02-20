from marshmallow import Schema, fields

class AccelerometerSchema(Schema):
    x = fields.Int(required=True)
    y = fields.Int(required=True)
    z = fields.Int(required=True)