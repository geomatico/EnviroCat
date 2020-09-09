from __future__ import absolute_import

from future import standard_library

standard_library.install_aliases()
from builtins import str
from builtins import range
from builtins import object
from qgis.PyQt.QtCore import QSettings, QTranslator, qVersion, QCoreApplication
from qgis.PyQt.QtWidgets import QAction, QTableWidgetItem, QMessageBox, QHeaderView, QWidget, QAbstractItemView
from qgis.PyQt.QtGui import QIcon, QTextCursor
# Initialize Qt resources from file resources.py
# Import the code for the dialog
from .gui import EnviroCatDialog, InfoDialog
# contains the webServiceObj Object to store the fields of a web service:
from .util.service_class import ServiceObject
# contains functions to help load in map servers:
# Library of functions to help with the loading in of OGC web services:
import os.path
import json, requests
import urllib.request, urllib.error, urllib.parse
from qgis.core import *


class EnviroCat(object):
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.
        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgisInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)


        # Create the dialogs and keep reference
        self.dlg = EnviroCatDialog()
        self.dlginfo = InfoDialog()
        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&EnviroCat')
        # TODO: We are going to let the user set this up in a future iteration
        self.toolbar = self.iface.addToolBar(u'EnviroCat')
        self.toolbar.setObjectName(u'EnviroCat')
        # define the datasets used:
        self.works = True  # will be used to determine whether the list url can be reached
        self.services = self.loadServiceList()
        if self.works == True:  # only sorts when the url worked
            self.services = self.sortServices(self.services)  # initialize and sort the services
            self.shownServices = self.services  # will change when serch criteria change to allow for the selected dataset to be found by row number

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.
        We implement this ourselves since we do not inherit QObject.
        :param message: String for translation.
        :type message: str, QString
        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('EnviroCat', message)

    ## add_action(self,icon_path,text,etc.) adds to the toolbar in QGIS's GUI
    def add_action(
            self,
            icon_path,
            text,
            callback,
            enabled_flag=True,
            add_to_menu=True,
            add_to_toolbar=True,
            status_tip=None,
            whats_this=None,
            parent=None):
        """Add a toolbar icon to the toolbar.
        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str
        :param text: Text that should be shown in menu items for this action.
        :type text: str
        :param callback: Function to be called when the action is triggered.
        :type callback: function
        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool
        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool
        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool
        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str
        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget
        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.
        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        # Create the dialog (after translation) and keep reference
        self.dlg = EnviroCatDialog()

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToWebMenu(
                self.menu,
                action)

        self.actions.append(action)

        return action

    ## initGui(self) is used here (after add_action call) to connect events to functions
    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = os.path.join(self.plugin_dir, 'icon', 'icon.png')
        self.add_action(
            icon_path,
            text=self.tr(u'EnviroCat'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # initialize event connections
        self.dlg.tableWidget.itemSelectionChanged.connect(self.updateDesc)
        self.dlg.close_btn.released.connect(self.dlg.close)
        self.dlg.load_btn.released.connect(self.loadWebService)
        self.dlg.searchBox.textEdited.connect(self.search)
        self.dlg.sortCombo.activated.connect(self.sortCurrentServices)
        self.dlg.info_btn.released.connect(self.openInfo)

    ## unload(self) removes the plugin from QGIS GUI
    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginWebMenu(
                self.tr(u'&EnviroCat'),
                action)
            self.iface.removeToolBarIcon(action)
        # remove the toolbar
        del self.toolbar

    # getSelectedServices(self) returns the web service object of the currently selected service in the table
    # getSelectedServices: CWS -> List of Services
    def getSelectedServices(self):
        """Gets the selected dataset from the table"""
        # get the number of the selected row:
        # rowNum = self.dlg.tableWidget.currentRow()
        rowNums = []
        selected = self.dlg.tableWidget.selectedItems()
        if (len(selected) > 0):
            for i in range(0, len(selected), 4):
                rowNums.append(self.dlg.tableWidget.row(selected[i]))

        selectedServices = []
        for row in rowNums:
            selectedServices.append(self.shownServices[row])

        # return the webServiceObj from the datasets list for that row
        return selectedServices

    # updateDesc(self) updates the description box with the name and description of the selected service
    # updateDesc: CWS -> None
    def updateDesc(self):
        # get the selected dataset:

        serv = self.getSelectedServices()
        # Gets the name of the last clicked service
        desc = serv[-1].desc if len(serv) > 0 else ""
        name = serv[-1].name if len(serv) > 0 else ""

        # update the description:
        self.dlg.textEdit.clear()
        cursor = QTextCursor(self.dlg.textEdit.document())
        cursor.insertText(name + "\n\n" + desc)

        self.dlg.textEdit.setReadOnly(True)

    # percentUp(self, up, down): returns the percent up time using up and down times
    # percentUp: CWS Float Float -> Int
    def percentUp(self, up, down):
        if up == 'null' or down == 'null' or up == 0:
            return 0
        elif down == 0:
            return 100
        total = up + down
        return int((up / total) * 100)

    # loadServiceList(self) returns a list of web services that meet the criteria of:
    #					Has a name, 20 or fewer layers, 90%+ weekly uptime, not WMTS
    # loadServiceList: CWS -> (listof Service) OR (listof None)
    # Modifies: When url can't be reached, self.works is set to false
    def loadServiceList(self):
        url = 'https://qgis.bioexplora.cat/script.json'
        response = requests.get(url)

        try:
            json_test = response.json()
        except:
            self.works = False  # this will be used in the run method to check if the url works
            # if it doesn't, an error message will appear on startup and the program will close
            return list()

        if self.works == True:
            response = response.text
            services = json.loads(response)

            webServicesList = []  # will hold web service objects

            for service in services:
                # get information needed to determine whether to include this service
                name = service['title']
                layers = service['layers']
                numLayers = len(layers)
                serviceType = service['serviceInterfaceType']  # to exclude WMTS services from being included
                if service[
                    'title'] != "" and serviceType != "WMTS":  # IMPORTANT*****************************************************************
                    # if its a good enough service, get the other fields and add it to the list
                    desc = service['abstract']
                    if serviceType == "ESRI_MapServer":
                        serviceType = "ESRI MapServer"
                    url = service['url']
                    # make a host url like the ones on the website using the url
                    host = urllib.parse.urlparse(url).hostname
                    # host = url[:url.index(".ca") + 3] # remove whats after '.ca'
                    # host = host[host.index("/") + 2:] # removes 'https://' or 'http://'
                    # directory = service['directoryUrl']
                    # create an object containing all the fields of a web service
                    webServiceObj = ServiceObject(name, host, desc, serviceType, url, layers, numLayers)
                    # add that object to our list of web service objects
                    webServicesList.append(webServiceObj)

            return webServicesList

    # setTableWidgetBehaviour(self) defines how tableWidget will behave
    # setTableWidgetBehaviour: CWS -> None
    def setTableWidgetBehaviour(self):
        # set row and column sizes and lock them
        self.dlg.tableWidget.setColumnWidth(0, 110)
        self.dlg.tableWidget.setColumnWidth(1, 110)
        self.dlg.tableWidget.setColumnWidth(2, 207)
        self.dlg.tableWidget.setColumnWidth(3, 86)
        self.dlg.tableWidget.horizontalHeader().setSectionResizeMode(QHeaderView.Fixed)
        self.dlg.tableWidget.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

        # self.dlg.tableWidget.resizeRowsToContents()

        # set event behaviors for the table
        self.dlg.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.dlg.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        # self.dlg.tableWidget.setSelectionMode(QAbstractItemView.MultiSelection) ************************* OLD SELECTION METHOD ************** CHOOSE WHAT YOU PREFER
        self.dlg.tableWidget.setSelectionMode(
            QAbstractItemView.ExtendedSelection)  # IF you uncomment the above line, comment this line, otherwise no changes will be seen

    # fill_table(self, serviceList): fills tableWidget with the services in serviceList
    # fill_table: CWS (listof Service) -> None
    def fill_table(self, serviceList):
        # initialize an empty table with 3 columns
        self.dlg.tableWidget.setRowCount(0)
        self.dlg.tableWidget.setColumnCount(4)

        for service in serviceList:
            index = serviceList.index(service)
            self.dlg.tableWidget.insertRow(index)  # inserts a blank row
            # lets fill that row:
            self.dlg.tableWidget.setItem(index, 0, QTableWidgetItem(service.name))  # fills in with the name
            self.dlg.tableWidget.setItem(index, 1,
                                         QTableWidgetItem(service.serviceType))  # fills in with the service type
            self.dlg.tableWidget.setItem(index, 2, QTableWidgetItem(service.host))  # fills in with the host
            self.dlg.tableWidget.setItem(index, 3,
                                         QTableWidgetItem(str(service.numLayers)))  # fills in with the number of layers

        # initialize the header labels
        self.dlg.tableWidget.setHorizontalHeaderLabels(["Nom", "Tipus", "Ubicacio", "# of Layers"])

        self.setTableWidgetBehaviour()

    # search(self) updates the displayed services (and self.shownServices) with only services
    #			  that contain the text in searchBox in their name, type, host, or number of layers
    # search: CWS -> None
    # Modifies: self.shownServices changes according to the text in searchBox
    #		   services in the table change to what is in self.shownServices
    def search(self):
        # clear description box
        self.dlg.textEdit.clear()
        # get entered text
        criteria = self.dlg.searchBox.text()
        criteria = criteria.lower()
        applicableServices = []  # will hold all services that meet the specified criteria
        # loops through all services
        for service in self.services:
            name = service.name.lower()
            host = service.host.lower()
            serviceType = service.serviceType.lower()
            # checks if the service meets the criteria in some way
            if (criteria in name) or (criteria in host) or (criteria in serviceType):
                applicableServices.append(service)
        # populates the table with only applicable services
        self.shownServices = applicableServices  # for description display and loading purposes
        self.sortCurrentServices()
        self.fill_table(applicableServices)

    # sortServices(self, servicesList) rearranges the services in ascending order based on
    #								  the selected sort field in sortCombo
    # sortServices: CWS (listof Service) -> (listof Service)
    # Modifies: table is filled with the sorted list of services
    def sortServices(self, servicesList):
        sortParam = self.dlg.sortCombo.currentText()
        # requires that these specific names are used in the sortCombo combo box
        if sortParam == "Name":
            servicesList.sort(key=lambda service: service.name.lower())
        elif sortParam == "Type":
            servicesList.sort(key=lambda service: service.serviceType)
        elif sortParam == "Host":
            servicesList.sort(key=lambda service: service.host)
        elif sortParam == "Layers":
            servicesList.sort(key=lambda service: service.numLayers)

        self.fill_table(servicesList)

        return servicesList

    # sortCurrentServices(self) acts as a wrapper for sortServices so it can be connected
    #						   to the change of sort type in sortCombo
    # sortCurrentServices: CWS -> (listof Service)
    # Modifies: table is filled with sorted version of self.shownServices
    def sortCurrentServices(self):
        # used for the sortCombo box because it can only take one parameter and will always use shownDatasets
        return self.sortServices(self.shownServices)

    # loadWebService(self): loads the selected service into the map layer by layer. If any layer
    #					   is not valid, a warning message will be displayed to the user
    # loadWebService: CWS -> None
    def loadWebService(self):

        # default projection, possibly changed later:
        EPSG_code = '4326'

        for serv in self.getSelectedServices():
            name = serv.name
            servType = serv.serviceType
            service_url = serv.url

            serviceErrors = False  # will become true if any of the layers cannot load in

            if servType == "WMS":

                # service_url = service_url[:-36] # simple way of removing the GetCapabilities request
                # wms = WebMapService(service_url)
                # layerList = list(wms.contents) # creates a list of the names of each layer in the service
                layerList = serv.layers
                numLayers = len(layerList)

                for layer in range(numLayers):
                    # construct a WMS url for the current layer
                    urlWithParams1 = 'url=' + str(service_url) + '&format=image/png&layers='
                    urlWithParams2 = '&styles=&crs=EPSG:' + str(EPSG_code)
                    urlWithParams = urlWithParams1 + layerList[layer]['name'] + urlWithParams2
                    # create the layer and add it to the map
                    rlayer = QgsRasterLayer(urlWithParams, layerList[layer]['title'], "wms")
                    if not rlayer.isValid():  # set service Errors to True if any layers can't be loaded
                        serviceErrors = True
                    QgsProject.instance().addMapLayer(rlayer)

            elif servType == "Vector":
                vlayer = QgsVectorLayer("/vsizip//vsicurl/" + serv.url, name, "ogr")
                if not vlayer.isValid():
                    print("Layer failed to load!")
                QgsProject.instance().addMapLayer(vlayer)

            elif servType == "Raster":
                rlayer = QgsRasterLayer("/vsicurl/" + serv.url, name)
                if not rlayer.isValid():
                    print("Layer failed to load!")
                QgsProject.instance().addMapLayer(rlayer)

            if serviceErrors == True:  # display an error message when one or more layers could not be loaded
                QMessageBox.warning(None, "Error Loading Layer(s)",
                                    "One or more of the layers from this service could not be loaded.")

    # openInfo(self) opens the info dialog
    # openInfo: CWS -> None
    def openInfo(self):
        self.dlginfo.show()

    def run(self):
        """Run method that performs all the real work"""
        if self.works == False:  # if the URL to load in the services wasn't working
            QMessageBox.warning(None, "WARNING",
                                "We couldn't reach our list of web services at this time. Please try again later.")
        # just show the user an error message and don't launch the plugin
        else:  # if all is well, continue on with opening the plugin
            self.shownServices = self.services  # reinitialize shownDatasets with all the datasets sorted by name
            self.dlg.sortCombo.setCurrentIndex(0)  # reset sortCombo to the Names option
            self.sortServices(self.services)  # reinitialize the table with all datasets sorted by name
            self.dlg.searchBox.clear()  # clear search box
            self.dlg.textEdit.clear()  # clear description box
            self.dlg.show()  # show the dialog

            # Run the dialog event loop
            result = self.dlg.exec_()

            # See if OK was pressed
            if result:
                # Do something useful here - delete the line containing pass and
                # substitute with your code.
                pass
