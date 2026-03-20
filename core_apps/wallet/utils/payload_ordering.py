"""
Utility functions to ensure consistent JSON key ordering for DTB API calls.

DTB hashes the request payload, so we must ensure identical key order
between initial request and SCA retry. PostgreSQL's JSONB field doesn't
preserve key order, so we explicitly define canonical ordering for each
transfer type.
"""
from collections import OrderedDict


# Define canonical key order for each transfer type
# These orders MUST match what was originally sent to DTB API

MPESA_KEY_ORDER = [
    'deliverToPhone',
    'reference',
    'amount',
    'callbackUrl',
    'description',
    'type',
    'externalUniqueId'
]

WALLET_TO_WALLET_KEY_ORDER = [
    'amount',
    'description',
    'externalUniqueId',
    'fromWalletId',
    'toWalletId'
]

PESALINK_KEY_ORDER = [
    'amount',
    'type',
    'description',
    'externalUniqueId',
    'accountNumber',
    'branchCode',
    'accountCurrency',
    'bank',
    'reference',
    'callbackUrl'
]

EFT_KEY_ORDER = [
    'accountName',
    'accountNumber',
    'branchCode',
    'bankCode',
    'amount',
    'callbackUrl',
    'description',
    'externalUniqueId',
    'location',
    'reference',
    'type',
    'currency'
]

IFT_KEY_ORDER = [
    'accountName',
    'accountNumber',
    'branchCode',
    'amount',
    'callbackUrl',
    'accountCurrency',
    'description',
    'type',
    'externalUniqueId'
]


def order_payload(payload_dict, key_order):
    """
    Reorder dictionary keys according to specified order.

    Args:
        payload_dict: Dictionary with payload data
        key_order: List of keys in desired order

    Returns:
        OrderedDict with keys in canonical order
    """
    ordered = OrderedDict()

    # Add keys in specified order
    for key in key_order:
        if key in payload_dict:
            ordered[key] = payload_dict[key]

    # Add any remaining keys not in key_order (shouldn't happen in normal operation)
    for key in payload_dict:
        if key not in ordered:
            ordered[key] = payload_dict[key]

    return ordered


def create_mpesa_payload(deliver_to_phone, reference, amount, callback_url,
                         description, external_unique_id):
    """
    Create MPESA withdrawal payload with canonical key order.

    Args:
        deliver_to_phone: Phone number to send money to
        reference: Transaction reference
        amount: Amount to transfer
        callback_url: Webhook URL for status updates
        description: Transfer description
        external_unique_id: Unique transaction ID

    Returns:
        OrderedDict with keys in canonical order matching DTB API expectations
    """
    return order_payload({
        'deliverToPhone': deliver_to_phone,
        'reference': reference,
        'amount': float(amount),
        'callbackUrl': callback_url,
        'description': description,
        'type': 'KE_DTB_MPESA',
        'externalUniqueId': str(external_unique_id)
    }, MPESA_KEY_ORDER)


def create_wallet_to_wallet_payload(amount, description, external_unique_id,
                                      from_wallet_id, to_wallet_id):
    """
    Create wallet-to-wallet transfer payload with canonical key order.

    Args:
        amount: Amount to transfer
        description: Transfer description
        external_unique_id: Unique transaction ID
        from_wallet_id: Source wallet ID
        to_wallet_id: Destination wallet ID

    Returns:
        OrderedDict with keys in canonical order
    """
    return order_payload({
        'amount': float(amount),
        'description': description,
        'externalUniqueId': str(external_unique_id),
        'fromWalletId': from_wallet_id,
        'toWalletId': to_wallet_id
    }, WALLET_TO_WALLET_KEY_ORDER)


def create_pesalink_payload(amount, description, external_unique_id,
                             account_number, branch_code, bank_code,
                             reference, callback_url):
    """
    Create PesaLink transfer payload with canonical key order.

    Args:
        amount: Amount to transfer
        description: Transfer description
        external_unique_id: Unique transaction ID
        account_number: Beneficiary account number
        branch_code: Bank branch code
        bank_code: Bank code
        reference: Transaction reference
        callback_url: Webhook URL for status updates

    Returns:
        OrderedDict with keys in canonical order
    """
    return order_payload({
        'amount': float(amount),
        'type': 'KE_DTB_PESALINK',
        'description': description,
        'externalUniqueId': str(external_unique_id),
        'accountNumber': account_number,
        'branchCode': branch_code,
        'accountCurrency': 'KES',
        'bank': bank_code,
        'reference': reference,
        'callbackUrl': callback_url
    }, PESALINK_KEY_ORDER)


def create_eft_payload(account_name, account_number, branch_code, bank_code,
                       amount, callback_url, description, external_unique_id,
                       reference):
    """
    Create EFT transfer payload with canonical key order.

    Args:
        account_name: Account holder name
        account_number: Beneficiary account number
        branch_code: Bank branch code
        bank_code: Bank code
        amount: Amount to transfer
        callback_url: Webhook URL for status updates
        description: Transfer description
        external_unique_id: Unique transaction ID
        reference: Transaction reference

    Returns:
        OrderedDict with keys in canonical order
    """
    return order_payload({
        'accountName': account_name,
        'accountNumber': account_number,
        'branchCode': branch_code,
        'bankCode': bank_code,
        'amount': float(amount),
        'callbackUrl': callback_url,
        'description': description,
        'externalUniqueId': str(external_unique_id),
        'location': 'kenya',
        'reference': reference,
        'type': 'KE_DTB_EFT',
        'currency': 'KES'
    }, EFT_KEY_ORDER)


def create_ift_payload(account_name, account_number, branch_code,
                      amount, callback_url, description, external_unique_id):
    """
    Create IFT transfer payload with canonical key order.

    Args:
        account_name: Account holder name
        account_number: Beneficiary account number
        branch_code: Bank branch code
        amount: Amount to transfer
        callback_url: Webhook URL for status updates
        description: Transfer description
        external_unique_id: Unique transaction ID

    Returns:
        OrderedDict with keys in canonical order
    """
    return order_payload({
        'accountName': account_name,
        'accountNumber': account_number,
        'branchCode': branch_code,
        'amount': float(amount),
        'callbackUrl': callback_url,
        'accountCurrency': 'KES',
        'description': description,
        'type': 'KE_DTB_IFT',
        'externalUniqueId': str(external_unique_id)
    }, IFT_KEY_ORDER)


def restore_payload_order(payload_dict, transfer_type):
    """
    Restore canonical key order for payload retrieved from database.

    PostgreSQL's JSONB field doesn't preserve key order. This function
    ensures the payload sent during SCA retry has the same key order as
    the initial request, which is critical for DTB's hash verification.

    Args:
        payload_dict: Payload dictionary retrieved from database
        transfer_type: Type of transfer (WALLET_TO_MPESA, WALLET_TO_WALLET, etc.)

    Returns:
        OrderedDict with keys restored to canonical order
    """
    if transfer_type == 'WALLET_TO_MPESA':
        return order_payload(payload_dict, MPESA_KEY_ORDER)
    elif transfer_type == 'WALLET_TO_WALLET':
        return order_payload(payload_dict, WALLET_TO_WALLET_KEY_ORDER)
    elif transfer_type == 'WALLET_TO_PESALINK':
        return order_payload(payload_dict, PESALINK_KEY_ORDER)
    elif transfer_type in ['WALLET_TO_BANK', 'WALLET_TO_EFT']:
        return order_payload(payload_dict, EFT_KEY_ORDER)
    elif transfer_type == 'WALLET_TO_IFT':
        return order_payload(payload_dict, IFT_KEY_ORDER)
    else:
        # Fallback: return as-is (shouldn't happen)
        return payload_dict
