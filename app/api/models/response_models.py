from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ErrorResponse(BaseModel):
    """Error response model"""
    status: str = "error"
    message: str
    error_code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Base success response model"""
    status: str = "success"
    message: Optional[str] = None


class TickDataResponse(SuccessResponse):
    """Response model for tick data requests"""
    data: List[Dict[str, Any]]
    count: int = Field(..., description="Number of records returned")
    stock_id: str = Field(..., description="Stock ID")
    start_date: str = Field(..., description="Start date of the data range")
    end_date: str = Field(..., description="End date of the data range")
    start_time: Optional[str] = Field(None, description="Start time filter (if applied)")
    end_time: Optional[str] = Field(None, description="End time filter (if applied)")
    convert_formats: bool = Field(True, description="Whether data formats were converted")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class LatestTickResponse(SuccessResponse):
    """Response model for latest tick data requests"""
    data: Optional[Dict[str, Any]] = None
    stock_id: str = Field(..., description="Stock ID")
    convert_formats: bool = Field(True, description="Whether data formats were converted")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class StockListResponse(SuccessResponse):
    """Response model for stock list requests"""
    stocks: List[str] = Field(..., description="List of stock IDs")
    count: int = Field(..., description="Number of stocks")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SubscriptionResponse(SuccessResponse):
    """Response model for subscription requests"""
    stock_id: str = Field(..., description="Stock ID")
    action: str = Field(..., description="Subscription action (add/remove)")
    convert_formats: bool = Field(True, description="Whether data formats will be converted")
    subscription_id: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PriceRoundingResponse(SuccessResponse):
    """Response model for price rounding requests"""
    original_price: float = Field(..., description="Original price")
    rounded_price: float = Field(..., description="Rounded price according to TSE rules")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class WebSocketSubscriptionModel(BaseModel):
    """Model for WebSocket subscription messages"""
    action: str = Field(..., description="Subscription action (subscribe/unsubscribe)")
    stock_id: str = Field(..., description="Stock ID")
    convert_formats: bool = Field(True, description="Whether to convert data formats")
    client_id: Optional[str] = None


class WebSocketDataModel(BaseModel):
    """Model for WebSocket data messages"""
    stock_id: str = Field(..., description="Stock ID")
    timestamp: str = Field(..., description="Timestamp of the data message")
    data: Dict[str, Any] = Field(..., description="Tick data")


class WebSocketConfirmationModel(BaseModel):
    """Model for WebSocket confirmation messages"""
    type: str = Field(..., description="Message type (connection_established, subscription_confirmation)")
    stock_id: Optional[str] = Field(None, description="Stock ID (for subscription confirmations)")
    convert_formats: Optional[bool] = Field(None, description="Format conversion preference (for subscription confirmations)")
    status: Optional[str] = Field(None, description="Subscription status (subscribed, unsubscribed)")
    client_id: Optional[str] = Field(None, description="Client ID (for connection confirmations)")
    message: Optional[str] = Field(None, description="Additional message")


class WebSocketErrorModel(BaseModel):
    """Model for WebSocket error messages"""
    type: str = "error"
    message: str = Field(..., description="Error message")
    error_code: Optional[str] = Field(None, description="Error code")