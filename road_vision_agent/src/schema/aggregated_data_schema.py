from marshmallow import Schema, fields
from schema.accelerometer_schema import AccelerometerSchema
from schema.gps_schema import GpsSchema

class AggregatedDataSchema(Schema):
    accelerometer = fields.Nested(AccelerometerSchema, required=True)
    gps = fields.Nested(GpsSchema, required=True)
    time = fields.DateTime('iso', required=True)