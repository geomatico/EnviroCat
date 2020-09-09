
# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load CanadianWebServices class from file CanadianWebServices.

    :param iface: A QGIS interface instance.
    :type iface: QgisInterface
    """
    #
    from .main import EnviroCat
    return EnviroCat(iface)
