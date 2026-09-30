"""
Wallet deposit request handler.
USDT BEP20 only — USD currency.
Flow: amount → payment details → screenshot → submit
"""

from decimal import Decimal, InvalidOperation

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database.engine import get_session
from bot.database.models.wallet_request import (
    PaymentMethod,
)
from bot.database.repositories import UserRepository
from bot.database.repositories.settings_repo import (
    SettingsRepository,
)
from bot.database.repositories.wallet_repo import (
    WalletRequestRepository,
)
from bot.keyboards.user.wallet import get_cancel_kb
from bot.keyboards.user.common import (
    get_back_menu_kb,
)
from bot.services.notification import (
    notification_service,
)
from bot.states.wallet_request import (
    WalletRequestStates,
)
from bot.utils.formatters import format_money
from bot.utils.helpers import escape_html
from bot.utils.logger import log

wallet_request_router = Router(
    name="wallet_request"
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — START DEPOSIT (skip method)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@wallet_request_router.callback_query(
    F.data == "wallet:deposit"
)
async def cb_start_deposit(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = "en",
    **kwargs,
) -> None:
    """Start deposit flow — ask amount in USDT."""

    # Auto-set USDT method
    await state.update_data(
        payment_method=PaymentMethod.USDT_BEP20.value
    )

    async with get_session() as session:
        settings = SettingsRepository(session)
        min_dep = await settings.get_float(
            SettingsRepository.KEY_MIN_DEPOSIT,
            default=1.0,
        )
        max_dep = await settings.get_float(
            SettingsRepository.KEY_MAX_DEPOSIT,
            default=10000.0,
        )

    await state.set_state(
        WalletRequestStates.entering_amount
    )

    await callback.message.edit_text(
        f"💲 <b>Add Balance (USDT)</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💰 Enter amount in <b>USDT</b>:\n\n"
        f"Min: <b>${min_dep}</b> | "
        f"Max: <b>${max_dep}</b>\n\n"
        f"Send the amount you want to deposit:",
        reply_markup=get_cancel_kb(),
    )
    await callback.answer()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2 — ENTER AMOUNT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@wallet_request_router.message(
    WalletRequestStates.entering_amount,
)
async def msg_enter_amount(
    message: Message,
    state: FSMContext,
    lang: str = "en",
    **kwargs,
) -> None:
    """Validate amount and show payment details."""

    if not message.text:
        await message.answer(
            "❌ Please send a number.",
            reply_markup=get_cancel_kb(),
        )
        return

    # Parse amount
    try:
        amount = Decimal(
            message.text.strip().replace(",", "")
        )
        if amount <= 0:
            raise ValueError
    except (InvalidOperation, ValueError):
        await message.answer(
            "❌ Invalid amount.\n"
            "Example: <code>10</code>",
            reply_markup=get_cancel_kb(),
        )
        return

    async with get_session() as session:
        settings = SettingsRepository(session)
        min_dep = Decimal(
            str(await settings.get_float(
                SettingsRepository.KEY_MIN_DEPOSIT,
                default=1.0,
            ))
        )
        max_dep = Decimal(
            str(await settings.get_float(
                SettingsRepository.KEY_MAX_DEPOSIT,
                default=10000.0,
            ))
        )

        # Validate limits
        if amount < min_dep or amount > max_dep:
            await message.answer(
                f"❌ Amount must be between "
                f"<b>${min_dep}</b> and "
                f"<b>${max_dep}</b>.",
                reply_markup=get_cancel_kb(),
            )
            return

        # Store amount (USD = USDT 1:1)
        await state.update_data(
            amount_usd=str(amount),
        )

        # Get USDT address
        usdt_address = await settings.get(
            SettingsRepository.KEY_USDT_BEP20_ADDRESS
        ) or "Not configured"

    text = (
        f"💲 <b>USDT Deposit</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📤 Send: <b>{amount} USDT</b>\n"
        f"💰 Credit: <b>${amount}</b>\n\n"
        f"🏦 <b>Network:</b> BEP20 (BSC)\n"
        f"📋 <b>Address:</b>\n"
        f"<code>{usdt_address}</code>\n\n"
        f"⚠️ Send <b>exact</b> amount only!\n"
        f"⚠️ Use <b>BEP20</b> network only!\n\n"
        f"After sending, upload screenshot."
    )

    await state.set_state(
        WalletRequestStates.uploading_screenshot
    )
    await message.answer(
        text,
        reply_markup=get_cancel_kb(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — UPLOAD SCREENSHOT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@wallet_request_router.message(
    WalletRequestStates.uploading_screenshot,
    F.photo,
)
async def msg_upload_screenshot(
    message: Message,
    state: FSMContext,
    lang: str = "en",
    **kwargs,
) -> None:
    """Save screenshot and submit request."""

    photo = message.photo[-1]
    file_id = photo.file_id

    await state.update_data(
        screenshot_file_id=file_id
    )

    # Submit directly (no UTR for USDT)
    await _submit_request(message, state, lang)


@wallet_request_router.message(
    WalletRequestStates.uploading_screenshot,
    ~F.photo,
)
async def msg_screenshot_not_photo(
    message: Message,
    **kwargs,
) -> None:
    """Handle non-photo uploads."""

    await message.answer(
        "❌ Please send a <b>screenshot</b> "
        "of your payment.",
        reply_markup=get_cancel_kb(),
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SUBMIT REQUEST
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def _submit_request(
    message: Message,
    state: FSMContext,
    lang: str,
) -> None:
    """Save request to DB and notify owner."""

    data = await state.get_data()
    await state.clear()

    user = message.from_user
    amount_usd = Decimal(
        data.get("amount_usd", "0")
    )
    screenshot_file_id = data.get(
        "screenshot_file_id"
    )

    async with get_session() as session:
        user_repo = UserRepository(session)
        db_user = (
            await user_repo.get_by_telegram_id(
                user.id
            )
        )

        req_repo = WalletRequestRepository(session)
        if await req_repo.has_pending(db_user.id):
            await message.answer(
                "⚠️ You already have a pending "
                "deposit request.\n"
                "Please wait for it to be processed.",
                reply_markup=get_back_menu_kb(lang),
            )
            return

        req = await req_repo.create(
            user_id=db_user.id,
            amount_inr=amount_usd,  # Store USD as amount_inr (re-used field)
            payment_method=PaymentMethod.USDT_BEP20,
            amount_usdt=amount_usd,
            usdt_rate=Decimal("1"),  # 1:1 USD = USDT
            screenshot_file_id=screenshot_file_id,
            utr_id=None,
        )

        await session.commit()
        request_id = req.id

    # Confirm to user
    await message.answer(
        f"✅ <b>Deposit Request Submitted!</b>\n\n"
        f"💰 Amount: <b>${format_money(amount_usd)}</b>\n"
        f"📋 Method: <b>USDT BEP20</b>\n"
        f"🔢 Request ID: <code>#{request_id}</code>\n\n"
        f"⏳ Your request is under review.\n"
        f"You'll be notified once approved.",
        reply_markup=get_back_menu_kb(lang),
    )

    # Notify owner
    await _notify_owner_new_request(
        request_id=request_id,
        user=user,
        amount_usd=amount_usd,
        screenshot_file_id=screenshot_file_id,
    )


async def _notify_owner_new_request(
    request_id: int,
    user,
    amount_usd: Decimal,
    screenshot_file_id,
) -> None:
    """Send deposit request notification to owner."""

    from bot.keyboards.owner.wallets import (
        get_request_action_kb,
    )

    name = escape_html(
        user.first_name
        or user.username
        or str(user.id)
    )
    username = (
        f"@{user.username}"
        if user.username
        else "No username"
    )

    text = (
        f"💲 <b>NEW DEPOSIT REQUEST</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 <b>{name}</b> ({username})\n"
        f"🆔 TG ID: <code>{user.id}</code>\n"
        f"🔢 Request: <code>#{request_id}</code>\n\n"
        f"💰 Amount: <b>${format_money(amount_usd)}</b>\n"
        f"📋 Method: <b>USDT BEP20</b>\n"
    )

    kb = get_request_action_kb(request_id)

    try:
        if screenshot_file_id:
            await notification_service.notify_owners_photo(
                photo=screenshot_file_id,
                caption=text,
                reply_markup=kb,
                setting_key=(
                    SettingsRepository
                    .KEY_BALANCE_REQ_NOTIF
                ),
            )
        else:
            await notification_service.notify_owners(
                text=text,
                reply_markup=kb,
                setting_key=(
                    SettingsRepository
                    .KEY_BALANCE_REQ_NOTIF
                ),
            )
    except Exception as e:
        log.error(f"❌ Owner notify failed: {e}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CANCEL
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@wallet_request_router.callback_query(
    F.data == "wallet:cancel_request"
)
async def cb_cancel_deposit(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = "en",
    **kwargs,
) -> None:
    """Cancel deposit flow."""

    await state.clear()

    try:
        await callback.message.delete()
    except Exception:
        pass

    await callback.answer(
        "❌ Cancelled", show_alert=False
    )

    await callback.message.answer(
        "❌ Deposit request cancelled.",
        reply_markup=get_back_menu_kb(lang),
    )