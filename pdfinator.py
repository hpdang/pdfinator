#!/usr/bin/env python

#_author_ = "Tom Lechner, Hong Phuc Dang, and Mario Behling"
#_copyright_ = "Copyright 2012" _credits_ = ["Tom Lechner", "Mario Behling", "Hong Phuc Dang"] 
#_license_ = "GPL"
#_version_ = "3.0" 
#_maintainer_ = "Mario Behling"
#_email_ = "mb@mariobehling.de" 
#_status_ = "Under Development"
#
#Pdfinator
#Create a pdf from a number of images.
#Uses ImageMagick convert to make non-jpegs into jpegs for inclusion.
#
#


##### TODO #####
#
#
#set orientation of each image
#capture chars for escape, control-q and control-w for quit
#set page size
#drag and drop files from nautilus
#
#DONE set gap size
#DONE reorder
#DONE icon previews
#DONE field for where to put pdf
#


DEFAULT_PAGESIZE="A4"



#Call in various necessary libraries
import pygtk
pygtk.require('2.0')

from PIL import Image
import gtk
import os
import subprocess
import sys
import datetime
import re




#---create an icon factory to work around IconView limitation (note: seems to not be needed after all, too lazy to remove)
ifactory = gtk.IconFactory()
ifactory.add_default()
iconnum = 0


papertypes=[["a4",      595,842],
            ["letter",  612, 792],
            ["legal",   612, 1008],
            ["tabloid", 1008,1224]
           ]

#Callback function to update preview in file picker, whenever a new file is selected
def update_preview_cb(file_chooser, preview):
  filename = file_chooser.get_preview_filename()
  try:
    pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(filename, 128, 128)
    preview.set_from_pixbuf(pixbuf)
    have_preview = True
  except:
    have_preview = False
  file_chooser.set_preview_widget_active(have_preview)
  return


#Called when you press the add button. Returns a list of files to add
def get_files_to_add():

    dialog = gtk.FileChooserDialog("Open..",
                                   None,
                                   gtk.FILE_CHOOSER_ACTION_OPEN,
                                   (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                    gtk.STOCK_OPEN, gtk.RESPONSE_OK))
    dialog.set_default_response(gtk.RESPONSE_OK)
    dialog.set_select_multiple(True)

    preview = gtk.Image()
    dialog.set_preview_widget(preview)
    dialog.connect("update-preview", update_preview_cb, preview)

    filter = gtk.FileFilter()
    filter.set_name("All files")
    filter.add_pattern("*")
    dialog.add_filter(filter)

    filter = gtk.FileFilter()
    filter.set_name("Images")
    filter.add_mime_type("image/png")
    filter.add_mime_type("image/jpeg")
    filter.add_mime_type("image/gif")
    filter.add_pattern("*.png")
    filter.add_pattern("*.jpg")
    filter.add_pattern("*.gif")
    filter.add_pattern("*.tif")
    filter.add_pattern("*.xpm")
    dialog.add_filter(filter)

    response = dialog.run()
    filenamelist=[]
    if response == gtk.RESPONSE_OK:
        print dialog.get_filenames(), 'selected'
        filenamelist=dialog.get_filenames()
    #elif response == gtk.RESPONSE_CANCEL:
    #    print 'Closed, no files selected'
    dialog.destroy()
    return filenamelist



#define some global constants
COL_PATH = 0
COL_PIXBUF = 1
COL_IS_DIRECTORY = 2

DEFAULT_IMAGE_WIDTH=100



#The main container for the application
class PyApp(gtk.Window): 
    def __init__(self):
        super(PyApp, self).__init__()
        
        self.set_size_request(700, 500)       #try to start the window this big
        self.set_position(gtk.WIN_POS_CENTER) #and center on screen
        
        self.connect("destroy", gtk.main_quit) #calls a standard quit function when necessary
        self.set_title("Pdfinator") #set title of the window
        
        self.current_directory = os.getcwd() 

        #Now build the window. It consists of:
        #  a gtk.Toolbar, with some big buttons like add, remove, make, etc...
        #  text input line to specify where the pdf should be generated
        #  IconView list of the images to make pdf from

        #----------make toolbar
        vbox = gtk.VBox(False, 0); #vbox is a container, a "vertical box" of windows or other boxes
       
        toolbar = gtk.Toolbar()
        vbox.pack_start(toolbar, False, False, 0)

         #create buttons and add to toolbar.
         #if you put "self." when defining them, the names are remembered
        self.addButton = gtk.ToolButton(gtk.STOCK_ADD);
        self.addButton.set_is_important(True)
        self.addButton.set_sensitive(True) #sensitive means if it's greyed out (false) or not (true)
        toolbar.insert(self.addButton, -1)
        self.addButton.connect("clicked", self.on_add_clicked)

        self.removeButton = gtk.ToolButton(gtk.STOCK_REMOVE);
        self.removeButton.set_is_important(True)
        self.removeButton.set_sensitive(True)
        toolbar.insert(self.removeButton, -1)
        self.removeButton.connect("clicked", self.on_remove_clicked)

        goButton = gtk.ToolButton(gtk.STOCK_GO_FORWARD)
        goButton.set_label("Make PDF")
        goButton.set_is_important(True)
        toolbar.insert(goButton, -1)
        goButton.connect("clicked", self.on_go_clicked)

        quitButton = gtk.ToolButton(gtk.STOCK_QUIT)
        quitButton.set_is_important(True)
        toolbar.insert(quitButton, -1)
        quitButton.connect("clicked", self.on_quit)


        #-------- make save to pdf line
        hbox = gtk.HBox(False,0)
        vbox.pack_start(hbox, False, False, 5)

        label = gtk.Label(" Save pdf to: ")
        hbox.pack_start(label, False, False, 0)

        self.pdfLocation = gtk.Entry()
        self.pdfLocation.set_text(os.path.expanduser("~")+"/new.pdf")
        hbox.pack_start(self.pdfLocation, True, True, 0)

        button = gtk.Button("...")
        hbox.pack_start(button, False, False, 0)
        button.connect("clicked", self.on_select_new_dest)

        #-------- make gap input
        label = gtk.Label(" Gap in pts: ")
        hbox.pack_start(label, False, False, 0)

        self.gapEntry = gtk.Entry()
        self.gapEntry.set_text("30")
        hbox.pack_start(self.gapEntry, False, False, 0)

        #--------icon view
        sw = gtk.ScrolledWindow()
        sw.set_shadow_type(gtk.SHADOW_ETCHED_IN)
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        vbox.pack_start(sw, True, True, 0)


		#self.fileIcon = self.get_icon(gtk.STOCK_FILE)
		#self.dirIcon = self.get_icon(gtk.STOCK_DIRECTORY)

        self.store = self.create_store()
        #self.fill_store()
        #self.fill_store_list(filenamelist)
        if (len(sys.argv)>1):
            for fl in sys.argv[1:len(sys.argv)]:
                self.add_to_store(fl)


        self.iconView = gtk.IconView(self.store)
        #self.iconView = gtk.TreeView(self.store)
        self.iconView.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.iconView.get_model().connect("row-inserted",self.on_rows_inserted)
        self.iconView.get_model().connect("row-deleted",self.on_rows_deleted)
        self.iconView.get_model().connect("rows-reordered",self.on_rows_reordered)

         #set up drag and drop
        self.iconView.enable_model_drag_dest([('text/plain', 0, 0)], gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE)
        self.iconView.connect("drag-data-received", self.drag_data_received_cb)

        self.iconView.set_text_column(COL_PATH)
        self.iconView.set_pixbuf_column(COL_PIXBUF)
        self.iconView.set_item_width(200) #this is NOT icon size
        self.iconView.set_reorderable(True)
        #self.iconView.set_reorderable(False)


        self.iconView.connect("item-activated", self.on_item_activated)
        sw.add(self.iconView)
        self.iconView.grab_focus()

        self.add(vbox)
        self.show_all()

    def drag_data_received_cb(self, iconview, context, x, y, selection, info, timestamp):
        #print "selection: ",selection
        #print "selection data: ",data
        #print "context: ",context
        #print "info: ",info
        #print "data type: ",selection.get_data_type()

         #dragging internally
        if selection.get_data_type()=='GTK_TREE_MODEL_ROW':
            data = selection.tree_get_row_drag_data()
            #print "data: ",data
            return


         #dragging in from outside
        if selection.get_data_type()=="text/plain":
            data = selection.get_data_uris()
            list=data.split('\n')
            print "dragged: ",list
            for l in list:
                l = l.replace("%20"," ")
                l = l.replace("file://","")
                l = l.replace("\n","")
                l = l.replace("\r","")
                print "Add dragged file: '"+l+"'"
                self.add_to_store(l)

#        drop_info = iconview.get_dest_item_at_pos(x, y)
#        if drop_info:
#            model = iconview.get_model()
#            path, position = drop_info
#            data = selection.data
#            print "selection data: ",data
#            # do something with the data and the model
#            #...
        return

    def get_icon(self, name):
        iconset = ifactory.lookup(name)
        if (iconset != None):
            return iconset.render_icon(gtk.Style(), gtk.TEXT_DIR_NONE, gtk.STATE_NORMAL, gtk.ICON_SIZE_LARGE_TOOLBAR, None, None)
        theme = gtk.icon_theme_get_default()
        return theme.load_icon(name, 48, 0)
    

    def create_store(self):
        store = gtk.ListStore(str, gtk.gdk.Pixbuf, bool)
        #store.set_sort_column_id(COL_PATH, gtk.SORT_ASCENDING)
        return store
            
    
     #add items from current directory
    def fill_store(self):
        self.store.clear()

        if self.current_directory == None:
            return

        for fl in os.listdir(self.current_directory):
        
            if not fl[0] == '.': 
                if os.path.isdir(os.path.join(self.current_directory, fl)):
                    self.store.append([fl, self.dirIcon, True])
                else:
                    self.store.append([fl, self.fileIcon, False])             
        
    
    def fill_store_list(self, list):
        self.store.clear()

        if self.current_directory == None:
            return

        for fl in list:
        
            if not fl[0] == '.': 
                if os.path.isdir(os.path.join(self.current_directory, fl)):
                    self.store.append([fl, self.dirIcon, True])
                else:
                    self.store.append([fl, self.fileIcon, False])             
        
    def add_to_store(self, fl):
        if (len(fl)==0): return
        if not os.stat(fl): return
        if not fl[0] == '.': 
            if os.path.isdir(os.path.join(self.current_directory, fl)):
                self.store.append([fl, self.dirIcon, True])
            else:
                #iconname = fl
                global iconnum
                global ifactory

                iconnum = iconnum + 1
                iconname = "test_"+str(iconnum)
                try:
                    pixbuf = gtk.gdk.pixbuf_new_from_file(fl)
                except:
                    print "Could not load "+fl+", skipping.."
                    return
                pix_w = pixbuf.get_width()
                pix_h = pixbuf.get_height()
                new_h = (pix_h * DEFAULT_IMAGE_WIDTH) / pix_w 
                scaled_pix = pixbuf.scale_simple(DEFAULT_IMAGE_WIDTH, new_h, gtk.gdk.INTERP_TILES)
                #model = self.iconView.get_model()
                #model.append((scaled_pix, im))
                self.store.append([fl, scaled_pix, False])             

    def add_to_store_list(self, list):
        for fl in list:
            self.add_to_store(fl)
        
    


    def on_go_clicked(self, widget):
        list=[]
        for row in self.store:
            list.append(row[0])
        #makePdfSimple(self.pdfLocation.get_text(), list)
        #makePdf(self.pdfLocation.get_text(), list, pagetype, gap)
        makePdf(self.pdfLocation.get_text(), list, DEFAULT_PAGESIZE, float(self.gapEntry.get_text()))

        message = gtk.MessageDialog(self, 0, gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO, "Done! Quit now?")
        status = message.run()
        if status == gtk.RESPONSE_YES:
            gtk.main_quit()
        #if status == gtk.RESPONSE_NO: print "no"
        message.destroy()
    
    def on_item_activated(self, widget, item):

        model = widget.get_model()
        path = model[item][COL_PATH]
        isDir = model[item][COL_IS_DIRECTORY]

        if not isDir:
            return
            
        self.current_directory = self.current_directory + os.path.sep + path
        self.fill_store()
        self.addButton.set_sensitive(True)
    

    def on_add_clicked(self, widget):
        self.current_directory = os.path.dirname(self.current_directory)
        list=get_files_to_add()
        self.add_to_store_list(list)
        #self.fill_store()
        sensitive = True
        self.addButton.set_sensitive(sensitive)

    def on_remove_clicked(self, widget):
        while True:
            items = self.iconView.get_selected_items()
            if not items:
                return
            model = self.iconView.get_model()
            item = items[0]
            iter = model.get_iter(item)

            print "remove: ",item,item[0]
            self.store.remove(iter)
        
    def on_rows_reordered(self, treemodel, b, c, d):
        print "reordered"

    def on_rows_inserted(self, treemodel, path, iter):
        print "inserted"

    def on_rows_deleted(self, treemodel, path):
        print "deleted"

    def on_select_new_dest(self, widget):
        dialog = gtk.FileChooserDialog("Open..",
                                       None,
                                       gtk.FILE_CHOOSER_ACTION_SAVE,
                                       (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                                        gtk.STOCK_SAVE, gtk.RESPONSE_OK))
        dialog.set_default_response(gtk.RESPONSE_OK)
        dialog.set_filename(self.pdfLocation.get_text())

        response = dialog.run()
        if response == gtk.RESPONSE_OK:
            filename=dialog.get_filename()
            self.pdfLocation.set_text(filename)
            #print dialog.get_filename(), 'selected'
        #elif response == gtk.RESPONSE_CANCEL:
            #print 'Closed, no files selected'
        dialog.destroy()

    def on_quit(self,widget):
        gtk.main_quit()
        #sys.exit(0)
    

 #Create a pdf on a particular size of paper, with given margin, images centered on the page, expanded to fill the margin area.
 #If the image is not a jpeg, we convert to jpeg first, with ImageMagick convert, and include the converted file.
 #
 #To understand what happens in this function, you might have to read the Pdf file format specification.
 #
 #pagetype will be something like "letter" or "a4", or "custom 234x432".
 #Custom pages are in points where 1 pt is 1/72 inch.
 #gap is in points, and pads the paper margins this much.
 #
 #Return 0 for success or nonzero for error.
def makePdf(pdffilename,filenamelist, pagetype, gap):
    (pagewidth,pageheight)=GetPaperSize(pagetype)
    rpagewidth  = pagewidth-2*gap
    rpageheight = pageheight-2*gap
    pageaspect=float(rpageheight)/rpagewidth

    #first go through the file list, find size and dimensions, and convert any that need converting to jpgs
    tounlink=[]
    info=[]
    tfilenum=0
    for file in filenamelist:
        img = Image.open(file)
        if not img: continue

        # get the image's width and height in pixels
        imgwidth, imgheight = img.size
        s=os.stat(file)

        fname,ext = os.path.splitext(file)
        if ext.lower() == ".jpg":
            info.append([file, imgwidth, imgheight, s.st_size])
            continue

        #else is non-jpg, need to convert
        tempfile = os.path.expanduser("~")+"/tempfileforpdfinator"+str(tfilenum)+".jpg"
        tfilenum = tfilenum + 1
        tounlink.append(tempfile)

        img.convert('RGB').save(tempfile, 'JPEG')
        s=os.stat(tempfile)

        #bg= Image.new('RGB', img.size, (255, 255, 255))
        #bg.paste(img,(0,0),img)
        #bg.save(tempfile) #saves as jpg

        #img.save(tempfile) #saves as jpg
        #   ^^^ **** breaks! mode of gif bad    

        info.append([tempfile, imgwidth, imgheight, s.st_size])


    pdf = open(pdffilename, "w")
    if not pdf:
        print "could not open ",pdffilename," for writing"
        return 1
    
    numpages=len(info)
    objectpos=[] #file positions of objects  

    #write pdf header
    pdf.write("%PDF-1.4\n"+
              "%\xff\xff\xff\xff\n")

    objectpos.append(pdf.tell())
    pdf.write("1 0 obj\n<<\n/Type /Catalog\n/Pages 3 0 R\n>>\nendobj\n")

    objectpos.append(pdf.tell())
    pdf.write("2 0 obj\n<<\n/ModDate("+str(datetime.datetime.now())+")\n/Producer(Pdfinator)\n>>\nendobj\n")


    #Each image adds 3 new objects:
    #  Page object
    #  Page content stream
    #  image xobject
    #
    #If the image is not a jpeg, we convert to jpeg first, with ImageMagick convert, to a temporary file

    #write out page list
    objectpos.append(pdf.tell())
    pdf.write("3 0 obj\n<<\n/Type /Pages\n/Count "+str(len(info))+"\n/Kids[")
    for num in range(4,4+numpages*3,3):
        pdf.write(str(num)+" 0 R ")
    pdf.write("]>>\nendobj\n")

    #now write out the 3 objects per file
    num = 4
    for imginfo in info:
        (file,wstr,hstr,imagesize) = imginfo
        imagewidth =float(wstr)
        imageheight=float(hstr)
        
        #first the page object
        objectpos.append(pdf.tell())
        pdf.write(str(num)+" 0 obj\n<<\n/Type /Page\n/Parent 3 0 R\n"+
                    "/Resources <</XObject <</image"+str(num+2)+" "+str(num+2)+" 0 R>> >>\n"+
                    "/Contents "+str(num+1)+" 0 R\n"+
                    "/MediaBox [0 0 "+str(pagewidth)+" "+str(pageheight)+"] >>\nendobj\n")

        #Next, the page's content stream
        aspect = float(imageheight)/imagewidth
        if aspect>pageaspect:
            scale=rpageheight/imageheight
        else:
            scale=rpagewidth/imagewidth
        rw=scale*imagewidth
        rh=scale*imageheight
        ox=pagewidth/2-rw/2
        oy=pageheight/2-rh/2

        objectpos.append(pdf.tell())
        num = num+1
        stream="q\n"+\
               str(scale)+" 0 0 "+str(scale)+" "+str(ox)+" "+str(oy)+" cm\n"+\
               str(imagewidth)+" 0 0 "+str(imageheight)+" 0 0 cm\n"+\
               "/image"+str(num+1)+" Do\n"+\
               "Q\n\n"
        pdf.write(str(num)+" 0 obj\n<</Length "+str(len(stream))+" >>\nstream\n"+stream+"\nendstream\nendobj\n")

        #finally, the image object
        objectpos.append(pdf.tell())
        num = num+1
        pdf.write(str(num)+" 0 obj\n"+
                    "<<\n"+
                    "  /Type /XObject\n"+
                    "  /Subtype /Image\n"+
                    "  /Width  "+str(int(imagewidth))+"\n"+
                    "  /Height "+str(int(imageheight))+"\n"+
                    "  /ColorSpace  /DeviceRGB\n"+
                    "  /BitsPerComponent  8\n"+
                    "  /Filter /DCTDecode\n"+
                    "  /Length "+str(imagesize)+"\n"+
                    ">>\n"+
                    "stream\n")
        #need to append contents of file to the new pdf.. It must be in jpg format for this to work..
        origfile=open(file,"rb")
        contents=origfile.read()
        pdf.write(contents)
        origfile.close()

        pdf.write("\nendstream\nendobj\n")
        num = num + 1
            
            

    #write out xref table
    xrefpos = pdf.tell()
    pdf.write("xref\n")
    pdf.write("0 "+str(1+len(objectpos))+"\n")
    pdf.write("0000000000 65535 f\n")
    for pos in objectpos:
        pdf.write("%010d 00000 n\n" % pos)

    #write trailer
    pdf.write("trailer\n"+
              "<</Info 2 0 R/Root 1 0 R/Size "+str(1+len(objectpos))+">>\n"
              "startxref\n"+
              str(xrefpos)+"\n"+
              "%%EOF")

    pdf.close()

    #final cleanup
    for file in tounlink:
        print " WARNING *** REMOVING ",file
        os.unlink(file)

    return 0

#Returns points in (w,h), where 1 point is 1/72 inch
def GetPaperSize(papername):
    #if papername[0:6] == "custom": .....
    if papername.lower()=="a4":      return (595,842)
    if papername.lower()=="letter":  return (612,792)
    if papername.lower()=="legal":   return (612,1008)
    if papername.lower()=="tabloid": return (1008,1224)


PyApp()
gtk.main()

