CREATE TABLE IF NOT EXISTS processed_agent_data (
  id SERIAL PRIMARY KEY,
  road_state VARCHAR(255) NOT NULL,
  x DOUBLE PRECISION,
  y DOUBLE PRECISION,
  z DOUBLE PRECISION,
  latitude DOUBLE PRECISION,
  longitude DOUBLE PRECISION,
  timestamp TIMESTAMP,
  -- For economic calculations (pothole size in cm)
  length DOUBLE PRECISION,
  width DOUBLE PRECISION,
  depth DOUBLE PRECISION,
  -- Computed repair cost (grn)
  cost DOUBLE PRECISION
);