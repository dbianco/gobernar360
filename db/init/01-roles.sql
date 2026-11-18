-- Role the API connects with. It owns no tables and cannot bypass row-level
-- security; migrations run as the owner role instead.
CREATE ROLE gobernar360_app LOGIN PASSWORD 'gobernar360_app';

-- Separate database for the automated test suite.
CREATE DATABASE gobernar360_test OWNER gobernar360;

-- Separate database for the browser end-to-end tests, which reset all data on every run.
CREATE DATABASE gobernar360_e2e OWNER gobernar360;
