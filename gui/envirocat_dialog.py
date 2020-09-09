import os

from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog

pluginPath = os.path.split(os.path.dirname(__file__))[0]
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    pluginPath, 'ui', 'envirocat.ui'))


class EnviroCatDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        """Constructor."""
        super(EnviroCatDialog, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://qt-project.org/doc/qt-4.8/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)
