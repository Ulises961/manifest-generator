import pytest
import torch
import logging

logger = logging.getLogger(__name__)

@pytest.fixture(scope="session")
def cuda_info():
    """Fixture to log CUDA environment information."""
    info = {
        "pytorch_version": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda
    }
    
    if torch.cuda.is_available():
        info["gpu_name"] = torch.cuda.get_device_name(0)
        info["device_count"] = torch.cuda.device_count()
    
    return info

@pytest.mark.gpu
def test_cuda_availability(cuda_info, caplog):
    """Test CUDA availability and proper initialization."""
    caplog.set_level(logging.INFO)
    
    # Log CUDA information
    for key, value in cuda_info.items():
        logger.info(f"{key}: {value}")
    
    try:
        assert torch.cuda.is_available(), "CUDA is not available"
        assert torch.cuda.device_count() > 0, "No CUDA devices found"
        
        device = torch.device('cuda')
        x = torch.randn(1).to(device)
        assert x.device.type == 'cuda', "Tensor not moved to CUDA"
    except AssertionError as e:
        pytest.skip(f"CUDA tests skipped: {str(e)}")