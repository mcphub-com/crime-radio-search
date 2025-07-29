# Crime_radio_search

## Introduction

Welcome to the crime_radio_search MCP! This mcp provides access to recent crime events and crime statistics for specific locations. Users can search for crime events based on zip codes, city PIDs, or GPS coordinates, and can also obtain statistical summaries for specified time periods. This documentation outlines the available endpoints and their functionalities.

## Tools Overview

### 1. search_crime_events

- **Name**: `search_crime_events`
- **Description**: Search for recent crime events using zipcode, city PID, or GPS coordinates. Returns crime events from the last 24 hours by default.

#### Input Schema

- `zipcode`: Zipcode to search for crime events. Can be a single zipcode like "95035" or multiple separated by commas. (Type: string or null)
- `city_pid`: City PID to search for crime events (e.g., "milpitas,california"). (Type: string or null)
- `latitude`: Latitude coordinate for geographic search. (Type: integer, number, or null)
- `longitude`: Longitude coordinate for geographic search. (Type: integer, number, or null)
- `radius_km`: Search radius in kilometers when using GPS coordinates. Default is 5km. (Type: integer, number, or null)
- `hours_back`: Number of hours back to search for events. Default is 24 hours (1 day). (Type: integer or null)
- `limit`: Maximum number of results to return. Default is 10, maximum is 100. (Type: integer or null)
- `category`: Filter by crime category (e.g., "Family Offense", "Theft", etc.). (Type: string or null)
- `risk_level`: Filter by risk level: "low", "medium", "high". (Type: string or null)

### 2. get_crime_stats

- **Name**: `get_crime_stats`
- **Description**: Get crime statistics and summaries for a specific location within the specified time period.

#### Input Schema

- `zipcode`: Zipcode to get crime statistics for. (Type: string or null)
- `city_pid`: City PID to get crime statistics for. (Type: string or null)
- `hours_back`: Number of hours back to analyze. Default is 24 hours. (Type: integer or null)
