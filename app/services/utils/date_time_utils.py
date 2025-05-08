from datetime import datetime, timedelta
from typing import Optional, List, Union
import logging

# Get logger
logger = logging.getLogger("tw_stock_api")

def format_date_to_yyyymmdd(date_str: str) -> str:
    """
    Format a date string to YYYYMMDD format.
    
    Args:
        date_str: Date string in various formats (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD)
        
    Returns:
        Formatted date string (YYYYMMDD)
        
    Raises:
        ValueError: If date format is invalid
    """
    try:
        if '-' in date_str:
            # Process YYYY-MM-DD format
            return datetime.strptime(date_str, '%Y-%m-%d').strftime('%Y%m%d')
        elif '/' in date_str:
            # Process YYYY/MM/DD format
            return datetime.strptime(date_str, '%Y/%m/%d').strftime('%Y%m%d')
        elif len(date_str) == 8 and date_str.isdigit():
            # Already in YYYYMMDD format
            return date_str
        else:
            raise ValueError(f"Invalid date format: {date_str}, please use YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD")
    except Exception as e:
        logger.error(f"Date format error: {e}")
        raise

def format_time_to_hhmmss(time_str: Optional[str]) -> str:
    """
    Format a time string to HHMMSS format or empty string.
    
    Args:
        time_str: Time string (HH:MM:SS, HHMMSS, HH:MM, or HHMM)
        
    Returns:
        Formatted time string (HHMMSS) or empty string
    """
    if not time_str:
        return ""
        
    # Remove separators and other non-digit characters
    clean_time = ''.join(c for c in time_str if c.isdigit())
    
    # Ensure time format is correct
    if len(clean_time) == 6:  # HHMMSS
        return clean_time
    elif len(clean_time) == 4:  # HHMM
        return clean_time + "00"
    elif len(clean_time) == 2:  # HH
        return clean_time + "0000"
    else:
        logger.warning(f"Unrecognized time format: {time_str}, no time filtering will be applied")
        return ""

def convert_timestamp_to_date(ts_str: str) -> str:
    """
    Convert a timestamp string to YYYY-MM-DD format.
    
    Args:
        ts_str: Timestamp string or value
        
    Returns:
        Formatted date string (YYYY-MM-DD) or original value if conversion fails
    """
    try:
        # Assume the timestamp is in milliseconds
        ts = int(ts_str)
        dt = datetime.fromtimestamp(ts)  # Convert to seconds level
        return dt.strftime('%Y-%m-%d')
    except (ValueError, TypeError) as e:
        logger.error(f"Timestamp conversion error: {e}, original value: {ts_str}")
        return ts_str  # Return original value if conversion fails

def format_display_time(time_input) -> str:
    """
    Format a numeric time to HH:MM:SS.ffffff format.
    
    Args:
        time_input: Numeric time (e.g. 93000123 -> 09:30:00.123000)
        
    Returns:
        Formatted time string (HH:MM:SS.ffffff)
    """
    try:
        # Convert to pure digital string
        digits = ''.join(c for c in str(time_input) if c.isdigit())
        if not digits:
            return ""

        # Process first 6 digits as HHMMSS, remainder as microseconds
        if len(digits) <= 6:
            digits = digits.zfill(6)
            hhmmss = digits
            micro = ""
        else:
            total_len = len(digits)
            hhmmss = digits[:total_len - 6].zfill(6)
            micro = digits[-6:].ljust(6, '0')[:6]

        # Format the time
        return f"{hhmmss[:2]}:{hhmmss[2:4]}:{hhmmss[4:6]}" + (f".{micro}" if micro else "")
    except Exception as e:
        logger.error(f"Display time format conversion error: {e}, original value: {time_input}")
        return str(time_input)

def get_date_range_files(data_root: str, start_date: str, end_date: str) -> List[str]:
    """
    Get file paths for all dates in the specified range.
    
    Args:
        data_root: Root directory for data files
        start_date: Start date (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD)
        end_date: End date (YYYY-MM-DD, YYYY/MM/DD, or YYYYMMDD)
        
    Returns:
        List of file paths for the date range
        
    Raises:
        ValueError: If date range is invalid
    """
    import os
    
    start_date = format_date_to_yyyymmdd(start_date)
    end_date = format_date_to_yyyymmdd(end_date)
    
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')
    
    # Ensure date range is valid
    if start_dt > end_dt:
        raise ValueError("Start date cannot be later than end date")
    
    # Ensure date range is within available data range
    earliest_date = datetime.strptime('20200302', '%Y%m%d')
    latest_date = datetime.strptime('20241231', '%Y%m%d')
    
    if start_dt < earliest_date:
        logger.warning(f"Start date is earlier than available data range (20200302), adjusted to earliest available date")
        start_dt = earliest_date
        
    if end_dt > latest_date:
        logger.warning(f"End date is later than available data range (20241231), adjusted to latest available date")
        end_dt = latest_date
    
    files = []
    current_dt = start_dt
    
    # Generate file paths for all dates in range
    while current_dt <= end_dt:
        file_date = current_dt.strftime('%Y%m%d')
        file_path = os.path.join(data_root, f'tw_orderbook_{file_date}.parquet')
        files.append(file_path)
        current_dt += timedelta(days=1)
        
    return files

def process_date_time_columns(df, convert_formats=True):
    """
    Process date and time columns in a DataFrame.
    
    Args:
        df: Pandas DataFrame containing date/time data
        convert_formats: Whether to convert to user-friendly formats
        
    Returns:
        DataFrame with processed date/time columns
    """
    import pandas as pd
    
    if df.empty:
        return df
    
    # Process date column
    if 'display_date' in df.columns:
        if convert_formats:
            # Convert timestamp to YYYY-MM-DD format
            df['display_date'] = df['display_date'].apply(convert_timestamp_to_date)
        else:
            # Just convert to string without changing format
            df['display_date'] = df['display_date'].astype(str)
            
    # Process time column
    if 'display_time' in df.columns:
        if convert_formats:
            # Convert to HH:MM:SS.ffffff format
            df['display_time'] = df['display_time'].apply(format_display_time)
        else:
            # Just convert to string without changing format
            df['display_time'] = df['display_time'].astype(str)
    
    return df