from decimal import Decimal, ROUND_HALF_UP
from typing import Union, Dict, Tuple, Optional
import logging
import pandas as pd
# Get logger
logger = logging.getLogger("tw_stock_api")

# Taiwan Stock Exchange price tick sizes
TW_PRICE_TICKS = [
    ((Decimal('0'), Decimal('10')), Decimal('0.01')),     # 0-10: 0.01
    ((Decimal('10'), Decimal('50')), Decimal('0.05')),    # 10-50: 0.05
    ((Decimal('50'), Decimal('100')), Decimal('0.1')),    # 50-100: 0.1
    ((Decimal('100'), Decimal('500')), Decimal('0.5')),   # 100-500: 0.5
    ((Decimal('500'), Decimal('1000')), Decimal('1.0')),  # 500-1000: 1.0
    ((Decimal('1000'), Decimal('9999999')), Decimal('5.0'))  # 1000+: 5.0
]

def round_to_tick_size(price: Union[float, Decimal, str]) -> Decimal:
    """
    Round a price to the nearest valid tick size based on Taiwan Stock Exchange rules.
    
    Args:
        price: The price to round (as float, Decimal, or str)
        
    Returns:
        Decimal: The price rounded to the nearest valid tick size
        
    Examples:
        >>> round_to_tick_size(5.123)
        Decimal('5.12')
        >>> round_to_tick_size(12.34)
        Decimal('12.35')
        >>> round_to_tick_size(75.67)
        Decimal('75.7')
        >>> round_to_tick_size(215.45)
        Decimal('215.5')
        >>> round_to_tick_size(620.75)
        Decimal('621.0')
        >>> round_to_tick_size(1234.56)
        Decimal('1235.0')
    """
    try:
        if not isinstance(price, Decimal):
            price = Decimal(str(price))  # Convert to Decimal for precise calculation
        
        # Find the appropriate tick size for this price range
        for (low, high), tick_size in TW_PRICE_TICKS:
            if low <= price < high:
                # Round to the nearest tick size using ROUND_HALF_UP
                return (price / tick_size).quantize(Decimal('1'), rounding=ROUND_HALF_UP) * tick_size
                
        # If no range matched (shouldn't happen with our ranges), return the original price
        logger.warning(f"No matching price range for {price}, returning unrounded value")
        return price
    except Exception as e:
        logger.error(f"Error rounding price {price}: {e}")
        # Return original price if conversion fails
        return price if isinstance(price, Decimal) else Decimal(str(price))

def process_price_columns(df, columns=None):
    """
    Process and round price columns in a DataFrame according to Taiwan Stock Exchange rules.
    
    Args:
        df: Pandas DataFrame containing price data
        columns: List of column names to process. If None, uses a default set of price columns.
        
    Returns:
        DataFrame with processed price columns
    """
    if df.empty:
        return df
        
    # Default price columns to check
    if columns is None:
        columns = [
            'bp_best_1', 'bp_best_2', 'bp_best_3', 'bp_best_4', 'bp_best_5', 
            'sp_best_1', 'sp_best_2', 'sp_best_3', 'sp_best_4', 'sp_best_5', 
            'trade_price'
        ]
    
    # Process only columns that exist in the DataFrame
    existing_columns = [col for col in columns if col in df.columns]
    
    for col in existing_columns:
        try:
            # Apply rounding to non-NaN values
            df[col] = df[col].apply(
                lambda x: round_to_tick_size(float(x)) if pd.notna(x) else x
            )
        except Exception as e:
            logger.error(f"Error processing price column {col}: {e}")
    
    return df

# Import pandas inside function to avoid circular imports
def process_volume_columns(df, columns=None):
    """
    Process volume columns in a DataFrame, converting to integers.
    
    Args:
        df: Pandas DataFrame containing volume data
        columns: List of column names to process. If None, uses a default set of volume columns.
        
    Returns:
        DataFrame with processed volume columns
    """
    import pandas as pd
    
    if df.empty:
        return df
        
    # Default volume columns to check
    if columns is None:
        columns = [
            'bv_best_1', 'bv_best_2', 'bv_best_3', 'bv_best_4', 'bv_best_5',
            'sv_best_1', 'sv_best_2', 'sv_best_3', 'sv_best_4', 'sv_best_5',
            'trade_volume'
        ]
    
    # Process only columns that exist in the DataFrame
    existing_columns = [col for col in columns if col in df.columns]
    
    for col in existing_columns:
        try:
            # Convert to integers for non-NaN values
            df[col] = df[col].apply(
                lambda x: int(x) if pd.notna(x) else x
            )
        except Exception as e:
            logger.error(f"Error processing volume column {col}: {e}")
    
    return df