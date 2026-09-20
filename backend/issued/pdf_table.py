from reportlab.platypus import Flowable, PageBreak, Table


class InvoiceItems(Table):
    def split(self, availWidth: float, availHeight: float) -> list[Flowable]:
        parts = super().split(availWidth, availHeight)
        if len(parts) == 2:
            return [parts[0], PageBreak(), parts[1]]
        return parts
