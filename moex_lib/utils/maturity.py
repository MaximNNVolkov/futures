from datetime import date

def months_to_maturity(today: date, maturity_date: date) -> int:
    """
    Возвращает количество ПОЛНЫХ месяцев до погашения
    """
    if maturity_date <= today:
        return -1

    months = (maturity_date.year - today.year) * 12 + (maturity_date.month - today.month)

    # если день погашения меньше сегодняшнего — месяц еще не полный
    if maturity_date.day < today.day:
        months -= 1

    return months
