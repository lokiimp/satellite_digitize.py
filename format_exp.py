def format_exp(val):
    if val == 0:
        return " 00000+0"
    exp = 0
    mant = val
    while abs(mant) < 1 and exp > -9:
        mant *= 10
        exp -= 1
    mant_int = int(round(abs(mant) * 1e4))  # abs here for safety
    # Format: sign/mantissa/exponent
    # leading space if positive, or '-' if negative value
    sign_char = " " if val >= 0 else "-"
    # mantissa is always 5 digits
    # exponent includes sign + digit
    exp_str = f"{exp:+d}"
    return f"{sign_char}{mant_int:05d}{exp_str}"

print(format_exp(0.00003025478374))
print(format_exp(0.0000030255983))
print(format_exp(0))
print(format_exp(-0.0004125493248))