import json
from datetime import datetime, timedelta, timezone
import traceback
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Union, Optional, List, Dict, Any
from typing import Annotated
from pymongo import MongoClient
import pymongo

mcp = FastMCP('crime-radio-search')

# MongoDB connection


def get_crime_collection():
    """Get crime event collection"""
    crime_col = MongoClient('mongodb://sandbox.mongos.pub.nb-sandbox.com').structure_data.crime_radio_event
    return crime_col

def parse_val(value, target_type):
    """Parse and convert value to target type with error handling"""
    if value is None:
        return None
    try:
        if target_type == str:
            return str(value)
        elif target_type == int:
            return int(value)
        elif target_type == float:
            return float(value)
        elif target_type == list:
            if isinstance(value, str):
                return [v.strip() for v in value.split(',')]
            return value if isinstance(value, list) else [value]
        else:
            return value
    except (ValueError, TypeError):
        return None

def build_geo_query(lat: float, lon: float, radius_km: float = 5.0) -> Dict[str, Any]:
    """Build MongoDB geo query for coordinates within radius"""
    return {
        "geopoint": {
            "$near": {
                "$geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "$maxDistance": radius_km * 1000  # Convert km to meters
            }
        }
    }

def build_time_query(hours_back: int = 24) -> Dict[str, Any]:
    """Build time range query for recent events"""
    # Ensure we're using UTC time for consistency
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours_back)
    
    # Remove timezone info for MongoDB compatibility if present
    return {
        "updated_at": {
            "$gte": start_time,
            "$lte": end_time
        }
    }

def serialize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Serialize MongoDB document for JSON response"""
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, datetime):
            serialized[key] = value.isoformat()
        elif isinstance(value, (int, float, str, bool, list, dict)):
            serialized[key] = value
        else:
            serialized[key] = str(value)
    return serialized

@mcp.tool()
def search_crime_events(
    zipcode: Annotated[Optional[str], Field(description='Zipcode to search for crime events. Can be a single zipcode like "95035" or multiple separated by commas.')] = None,
    city_pid: Annotated[Optional[str], Field(description='City PID to search for crime events (e.g., "milpitas,california").')] = None,
    latitude: Annotated[Optional[Union[int, float]], Field(description='Latitude coordinate for geographic search.')] = None,
    longitude: Annotated[Optional[Union[int, float]], Field(description='Longitude coordinate for geographic search.')] = None,
    radius_km: Annotated[Optional[Union[int, float]], Field(description='Search radius in kilometers when using GPS coordinates. Default is 5km.')] = 5.0,
    hours_back: Annotated[Optional[int], Field(description='Number of hours back to search for events. Default is 24 hours (1 day).')] = 24,
    limit: Annotated[Optional[int], Field(description='Maximum number of results to return. Default is 10, maximum is 100.')] = 10,
    category: Annotated[Optional[str], Field(description='Filter by crime category (e.g., "Family Offense", "Theft", etc.).')] = None,
    risk_level: Annotated[Optional[str], Field(description='Filter by risk level: "low", "medium", "high".')] = None
) -> Dict[str, Any]:
    '''Search for recent crime events using zipcode, city PID, or GPS coordinates. Returns crime events from the last 24 hours by default.'''
    
    try:
        # Parse parameters
        zipcode_val = parse_val(zipcode, str)
        city_pid_val = parse_val(city_pid, str)
        latitude_val = parse_val(latitude, float)
        longitude_val = parse_val(longitude, float)
        radius_val = parse_val(radius_km, float) or 5.0
        hours_val = parse_val(hours_back, int) or 24
        limit_val = min(parse_val(limit, int) or 10, 100)  # Cap at 100
        category_val = parse_val(category, str)
        risk_val = parse_val(risk_level, str)
        
        # Build query
        query = {}
        
        # Add time filter (always included)
        query.update(build_time_query(hours_val))
        
        # Add location filters
        location_filters = []
        
        if zipcode_val:
            zipcodes = [z.strip() for z in zipcode_val.split(',')]
            # Match if any element in the document's zipcodes overlaps with the query list
            location_filters.append({"zipcodes": {"$elemMatch": {"$in": zipcodes}}})
        
        if city_pid_val:
            location_filters.append({"city_pid": city_pid_val})
        
        if latitude_val is not None and longitude_val is not None:
            location_filters.append(build_geo_query(latitude_val, longitude_val, radius_val))
        
        # Combine location filters with OR if multiple
        if location_filters:
            if len(location_filters) == 1:
                query.update(location_filters[0])
            else:
                query["$or"] = location_filters
        
        # Add category filter
        if category_val:
            query["category"] = {"$regex": category_val, "$options": "i"}
        
        # Add risk level filter
        if risk_val and risk_val.lower() in ['low', 'medium', 'high']:
            query["risk"] = risk_val.lower()
        query['address_type'] = 'POI'
        # Get collection and execute query
        collection = get_crime_collection()
        # Execute query with sorting by updated_at (most recent first)
        cursor = collection.find(query).sort("updated_at", -1).limit(limit_val)
        # Convert results to list and serialize
        results = []
        for doc in cursor:
            results.append(serialize_document(doc))
        
        return {
            "success": True,
            "query": query,
            "query_params": {
                "zipcode": zipcode_val,
                "city_pid": city_pid_val,
                "latitude": latitude_val,
                "longitude": longitude_val,
                "radius_km": radius_val,
                "hours_back": hours_val,
                "limit": limit_val,
                "category": category_val,
                "risk_level": risk_val
            },
            "results_count": len(results),
            "results": results
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Search failed: {traceback.format_exc()}",
            "query_params": {
                "zipcode": zipcode,
                "city_pid": city_pid,
                "latitude": latitude,
                "longitude": longitude,
                "radius_km": radius_km,
                "hours_back": hours_back,
                "limit": limit,
                "category": category,
                "risk_level": risk_level
            },
            "results_count": 0,
            "results": []
        }

@mcp.tool()
def get_crime_stats(
    zipcode: Annotated[Optional[str], Field(description='Zipcode to get crime statistics for.')] = None,
    city_pid: Annotated[Optional[str], Field(description='City PID to get crime statistics for.')] = None,
    hours_back: Annotated[Optional[int], Field(description='Number of hours back to analyze. Default is 24 hours.')] = 24
) -> Dict[str, Any]:
    '''Get crime statistics and summaries for a specific location within the specified time period.'''
    
    try:
        # Parse parameters
        zipcode_val = parse_val(zipcode, str)
        city_pid_val = parse_val(city_pid, str)
        hours_val = parse_val(hours_back, int) or 24
        
        # Build base query
        query = build_time_query(hours_val)
        
        # Add location filter
        if zipcode_val:
            zipcodes = [z.strip() for z in zipcode_val.split(',')]
            # Match if any element in the document's zipcodes overlaps with the query list
            query["zipcodes"] = {"$elemMatch": {"$in": zipcodes}}
        elif city_pid_val:
            query["city_pid"] = city_pid_val
        query['address_type'] = 'POI'
        # Get collection
        collection = get_crime_collection()
        
        # Get aggregation pipeline for statistics
        pipeline = [
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "total_events": {"$sum": 1},
                    "categories": {"$addToSet": "$category"},
                    "risk_levels": {"$push": "$risk"},
                    "avg_audio_duration": {"$avg": "$audio_duration"},
                    "latest_event": {"$max": "$updated_at"},
                    "earliest_event": {"$min": "$updated_at"}
                }
            }
        ]
        
        # Execute aggregation
        stats_result = list(collection.aggregate(pipeline))
        
        if not stats_result:
            return {
                "success": True,
                "location": {"zipcode": zipcode_val, "city_pid": city_pid_val},
                "time_period_hours": hours_val,
                "total_events": 0,
                "statistics": {}
            }
        
        stats = stats_result[0]
        
        # Calculate risk level distribution
        risk_distribution = {}
        for risk in stats.get("risk_levels", []):
            risk_distribution[risk] = risk_distribution.get(risk, 0) + 1
        
        return {
            "success": True,
            "location": {"zipcode": zipcode_val, "city_pid": city_pid_val},
            "time_period_hours": hours_val,
            "total_events": stats.get("total_events", 0),
            "statistics": {
                "categories": stats.get("categories", []),
                "risk_distribution": risk_distribution,
                "avg_audio_duration": round(stats.get("avg_audio_duration", 0), 2),
                "latest_event": stats.get("latest_event").isoformat() if stats.get("latest_event") else None,
                "earliest_event": stats.get("earliest_event").isoformat() if stats.get("earliest_event") else None
            }
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Statistics query failed: {str(e)}",
            "location": {"zipcode": zipcode, "city_pid": city_pid},
            "time_period_hours": hours_back,
            "total_events": 0,
            "statistics": {}
        }

def run_test():
    """Test function to validate the search functionality"""
    try:
        # Test zipcode search
        result = search_crime_events(zipcode="95035", hours_back=24, limit=5)
        print("Zipcode search test:")
        print(f"Success: {result['success']}")
        print(f"Results count: {result['results_count']}")
        
        # Test city_pid search
        result = search_crime_events(city_pid="milpitas,california", hours_back=48, limit=3)
        print("\nCity PID search test:")
        print(f"Success: {result['success']}")
        print(f"Results count: {result['results_count']}")
        
        # Test GPS search
        result = search_crime_events(latitude=37.44604959999999, longitude=-121.8326357, radius_km=2.0, hours_back=12)
        print("\nGPS search test:")
        print(f"Success: {result['success']}")
        print(f"Results count: {result['results_count']}")
        
        # Test statistics
        stats = get_crime_stats(city_pid="milpitas,california", hours_back=24)
        print("\nStatistics test:")
        print(f"Success: {stats['success']}")
        print(f"Total events: {stats['total_events']}")
        
    except Exception as e:
        print(f"Test failed: {str(e)}")

if __name__ == "__main__":
    # Uncomment to run tests
    # run_test()
    mcp.run(transport="stdio")