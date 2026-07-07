from upi_dispute_app.pii import mask_upi_id


def test_mask_upi_id_masks_handle_but_keeps_provider() -> None:
    assert mask_upi_id("customername@upi") == "cu***e@upi"


def test_mask_upi_id_handles_short_handle() -> None:
    assert mask_upi_id("ab@bank") == "a***@bank"
