"""
Energy Rental API Endpoint

Provides energy rental service for TRON transactions:
- Testnet: Simulates rental and shows educational information
- Mainnet: Integrates with real energy rental platforms (future)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Literal
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class EnergyRentalRequest(BaseModel):
    """Request to rent energy for a transaction."""
    transaction: dict
    recipient_address: str
    network: Literal["mainnet", "nile", "shasta"]
    estimated_energy: int


class EnergyRentalResponse(BaseModel):
    """Response from energy rental service."""
    success: bool
    mode: Literal["simulated", "rented", "failed"]
    message: str
    energy_amount: int
    cost_sun: Optional[int] = None
    cost_trx: Optional[float] = None
    savings_percentage: Optional[float] = None
    rental_txid: Optional[str] = None


@router.post("/rent-energy", response_model=EnergyRentalResponse)
async def rent_energy(request: EnergyRentalRequest) -> EnergyRentalResponse:
    """
    Rent energy for a TRON transaction.
    
    - Testnet: Returns simulation with educational information
    - Mainnet: Attempts real energy rental (future implementation)
    """
    
    logger.info(f"Energy rental request: network={request.network}, energy={request.estimated_energy}")
    
    # Testnet mode: Simulate rental
    if request.network in ["nile", "shasta"]:
        logger.info("Testnet mode: Simulating energy rental")
        
        # Calculate what it would cost on mainnet
        # Approximate: 1 TRX = 1,000,000 SUN
        # Energy price on mainnet: ~40-60 SUN per energy
        # Using 50 SUN as average
        estimated_cost_sun = request.estimated_energy * 50
        estimated_cost_trx = estimated_cost_sun / 1_000_000
        
        # Compare to burning TRX (280 SUN per energy)
        burn_cost_sun = request.estimated_energy * 280
        burn_cost_trx = burn_cost_sun / 1_000_000
        
        # Calculate savings
        savings_sun = burn_cost_sun - estimated_cost_sun
        savings_trx = burn_cost_trx - estimated_cost_trx
        savings_percentage = (savings_sun / burn_cost_sun) * 100 if burn_cost_sun > 0 else 0
        
        return EnergyRentalResponse(
            success=True,
            mode="simulated",
            message=(
                f"💡 Testnet simulation: On mainnet, renting {request.estimated_energy:,} energy "
                f"would cost ~{estimated_cost_trx:.2f} TRX and save ~{savings_trx:.2f} TRX "
                f"({savings_percentage:.0f}% savings) compared to burning TRX. "
                f"Proceeding with normal transaction on testnet."
            ),
            energy_amount=request.estimated_energy,
            cost_sun=estimated_cost_sun,
            cost_trx=estimated_cost_trx,
            savings_percentage=savings_percentage
        )
    
    # Mainnet mode: Real rental (to be implemented)
    elif request.network == "mainnet":
        logger.warning("Mainnet energy rental not yet implemented")
        return EnergyRentalResponse(
            success=False,
            mode="failed",
            message="Mainnet energy rental coming soon! Please proceed with normal transaction.",
            energy_amount=request.estimated_energy
        )
    
    else:
        raise HTTPException(status_code=400, detail=f"Unknown network: {request.network}")
