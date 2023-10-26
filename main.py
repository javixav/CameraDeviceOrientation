from os import replace, environ, mkdir
from os.path import join, basename, exists
from kivymd.uix.imagelist import MDSmartTile
from kivymd.app import MDApp
from kivy.lang import Builder
from kivymd.uix.screenmanager import MDScreenManager
from kivy.properties import StringProperty, ObjectProperty, ColorProperty, BooleanProperty,NumericProperty
from kivy.clock import Clock, mainthread
from kivy.utils import platform
from kivy.logger import Logger
from android_permissions import AndroidPermissions
from camera4kivy import Preview
from kivymd.uix.screen import MDScreen
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.label import Label
from PIL import Image
from shutil import copyfile
from kivy.graphics import Color
from kivymd.toast import toast

'''
Goal to this repo :
Make an android app that takes a picture from the 4 orientations which are
    ["portrait","landscape","reverse-portrait","reverse-landscape"]
and display the picture in the correct orientation

There are a lot of comments here, to explained the process, some can be deprecated
We finally resolve the error displaying pictures in -90° thanks to java SensorEventListener
Plus we find how to save images to Document's folder thanks to androidstorage4kivy

Done : 

    2. In portrait/portrait-reverse, there is a black line surrounding the picture
        a. Try to set letterbox_color: [1,1,1,1] in Preview Widget
            1. letterbox_color: [1,1,1,1] # does nothing
            2. letterbox_color: Color_Property("white") # bug invalid format
            3. letterbox_color: Color_Property([1,1,1,1]) #  bug invalid format
            result : a does nothing
            
        b. test aspect_ratio: '16:9' # does nothing to the black line but the preview image is fullscreen and 
            there is a zoom.

        c. Try to isolate the issue : It was PIL, and expand = True fixed the issue !!!

     1. Timing after capture, a bit long
        a.Try to move the saving the shared part after closing screen
            Not much impact
        b. try threading as photo are taken in another thread
            threading is not as good as we thought, introduce some unexpected behaviour
            like, saving a file with suffixe (1)
            or not starting disconnect camera method
        c. try with disconnecting the camera
            we thread the disconnecting camera and gain 1s !
            yes but in reality it was not disconnecting the camera
            so we just move the self.disconnect from the end to the beginning

        d. in connect_camera(optimize = "latency", default is "quality")
            Not much impact in timing only that quality picture is bad
        
        f. if in connect camera (enable_analyze_pixels = True) and enable_video = False
            decrease analyse frame rate : https://github.com/Android-for-Python/Camera4Kivy#performance
            by reducing analyze_pixels_resolution in connect camerera (analyze_pixels_resolution = 1024, try 720)
            see QRreader project see https://github.com/Android-for-Python/c4k_tflite_example/blob/main/classifyobject.py

                Not much impact...
        g. Try adding self.ids.image.nocache = True to Image Widget
            Not much impact...
    
   5. Add flash and torch icons

To do :      
        
    3. Play with orientation prop and change it to corresponding orientation just before capturing see doc 
    https://github.com/Android-for-Python/Camera4Kivy#cropped-sensor-resolution
    orientation_prop = ["portrait", "landscape","same","opposite"] default "same"
    The choice modifies resolution, best resolution is always obtained with "same"

    4. Play with inhibit_property
        default True
        connecting camera makes inhibit_property True while disconnecting False
        has an effect in function on orientation and on aspect ratio
        to play with we need to entrirely override def connect_camera
'''


if platform == "android":
    from android.storage import app_storage_path, primary_external_storage_path
    from android import mActivity, api_version, autoclass, cast
    from androidstorage4kivy import SharedStorage
    Environment = autoclass('android.os.Environment')
    ContentValues = autoclass('android.content.ContentValues')
    MediaStoreMediaColumns = autoclass('android.provider.MediaStore$MediaColumns')
    FileInputStream = autoclass('java.io.FileInputStream')
    FileUtils = autoclass('android.os.FileUtils')
    ContentUris = autoclass('android.content.ContentUris')
    MediaStoreFiles = autoclass('android.provider.MediaStore$Files')
    DeviceOrientation = autoclass("org.kivy.orientation.DeviceOrientation")

'''
To make the script working from scratch don't forget:

    For camera4kivy add camerax_provider folder if not already exists : 
        cd <project directory>
        git clone https://github.com/Android-for-Python/camerax_provider.git
        rm -rf camerax_provider/.git

        buildozer.spec:
        android.api = 33 (Constrained by Android packages imported by camerax_provider)
        requirements=python3, kivy==master, https://github.com/kivymd/KivyMD/archive/master.zip, pillow,camera4kivy, gestures4kivy, androidstorage4kivy
        p4a.hook = camerax_provider/gradle_options.py

    For SensorEventListener to get Device Orientation : 
        add folder java with DeviceOrientation.java
        and in spec file : android.add_src = java

All this is already done in githu repo
'''

def log(msg):
    Logger.info(msg)

KV = '''

<FlashIcons>:
    markup: True
    icon_active: (0.13, 0.58, 0.95, 0.8)
    icon_inactive: (0.43, 0.43, 0.43, 0.8)

    canvas.before:
        Color:
            rgba: self.icon_active if self.active else self.icon_inactive
        Ellipse
            pos: self.pos
            size: self.size

    size_hint: None, None
    size: dp(30), dp(30)
    font_size: dp(30)/2

<CameraShootButton>:
    markup: True
    text: u"[font=images/pic_icon.ttf]\ue800[/font]"
    icon_color: (0.13, 0.58, 0.95, 0.8)
    _down_color: self.darker(self.icon_color)

    canvas.before:
        Color:
            rgba: self.icon_color if self.state == 'normal' else self._down_color
        Ellipse:
            pos: self.pos
            size: self.size

    size_hint: None, None
    size: dp(70), dp(70)
    font_size: dp(70)/2

<MyMDSmartTile>:
    radius: 24
    box_radius: 0, 0, 24, 24 
    box_color: 0, 0, 0, .5
    size_hint: 1, None
    # width: "120dp"
    height: "160dp" 
    mipmap: False 

    MDIconButton:
        icon: "camera"
        on_release: 
            app.root.ids._picture_screen.tile = root
            app.root.ids._picture_screen.picture_name = root.text
            app.root.current = "picture_screen"

    MDLabel:
        text: root.text
        bold: True
        font_style: "Caption"
        opposite_colors: True

MyMDScreenManager:
    MDScreen:
        name: "home_screen"

        MDSwiper:
            size_hint_y: None
            height: root.height - dp(40)
            y: root.height - self.height - dp(10)
            items_spacing: 0 # the space between each items default dp(20)

            MDSwiperItem:
                MDScrollView:
                    MDGridLayout:
                        id: _mybox
                        cols: 2
                        adaptive_height: True
                        padding:10 # 40
                        spacing:10 # 20

            MDSwiperItem:
                MDScrollView:
                    MDBoxLayout:
                        orientation: "vertical"
                        adaptive_height: True
                        MDGridLayout:
                            cols:2
                            adaptive_height: True
                            MDLabel:
                                adaptive_width: True 
                                text: "cache image Unused"
                            MDSwitch:
                                active: True
                                on_active: 
                                    root.ids._picture_screen.cache = self.active

    PictureMDScreen:
        id: _picture_screen
        name: "picture_screen"
        root: root
        photo_preview: _preview
        torch: _torch
        MDFloatLayout:
            MyPreview:
                id: _preview
                screen: _picture_screen
            CameraShootButton:
                pos_hint: {"center_x": .5, "center_y": .2}
                on_release:
                    _preview.capture_photo(location = "private", subdir = "images", name = _picture_screen.picture_name) # or capture_screenshot()
            FlashIcons:
                id: _noflash
                text: u"[font=images/flash-icons.ttf]\u0062[/font]"
                pos_hint: {"center_x":.6, "top":.95}
                active: True
                on_release: 
                    self.active = True
                    _flash.active = False
                    _autoflash.active = False
                    _preview.flash(state = 'off')
            FlashIcons:
                id: _flash
                text: u"[font=images/flash-icons.ttf]\u0063[/font]"
                pos_hint: {"center_x":.7, "top":.95}
                on_release: 
                    self.active = True
                    _noflash.active = False
                    _autoflash.active = False
                    _preview.flash(state = 'on')
                
            FlashIcons:
                id: _autoflash
                text: u"[font=images/flash-icons.ttf]\u0064[/font]"
                pos_hint: {"center_x":.8, "top":.95}
                on_release: 
                    self.active = True
                    _noflash.active = False
                    _flash.active = False
                    _preview.flash(state = 'auto')

            FlashIcons:
                id: _torch
                text: u"[font=images/torch.ttf]\u0061[/font]"
                pos_hint: {"center_x":.9, "top":.95}
                on_release: 
                    self.active = False if self.active else True
                    _preview.torch(state = 'on') if self.active else _preview.torch(state = 'off')   
'''

class FlashIcons(ButtonBehavior, Label):
    active = BooleanProperty(False)

    def on_active(self,*args):
        if self.active:
            with self.canvas.before:
                Color(rgba = self.icon_active)
        else:
            with self.canvas.before:
                Color(rgba = self.icon_inactive)

if platform == "android":
    class MySharedStorage(SharedStorage):
        '''
        Override Class SharedStorage, to save picture not in Android Picture Collection but in Documents
        '''

        def copy_to_shared(self, private_file, collection = None, filepath = None):
            if private_file == None or not exists(private_file):
                return None
            file_name = basename(private_file) # basename("folder1.file1.text") returns file1.txt
            MIME_type = "text/plain"
            auto_collection = self._get_auto_collection(MIME_type) # return collection from mimetype here "Documents" (Environment.DIRECTORY_DOCUMENTS)
            if not self._legal_collection(auto_collection, collection): # check if arg collection correct
                collection = auto_collection
            path = [collection, self.get_app_title()] # ["Documents","appname"]

            if filepath: # "fold1/fold2/file1.txt"
                sfp = filepath.split('/') # ["fold1","fold2","file1.txt"]
                file_name = sfp[-1] # "file1.txt"
                for f in sfp[:-1]:
                    path.append(f) # ["Documents","appname","fold1","fold2"]

            if api_version > 28:
                sub_directory = ''
                for d in path:
                    sub_directory = join(sub_directory,d) # "Documents/appname/fold1/fold2"
                uri = self._get_uri(join(sub_directory, file_name)) 
                context = mActivity.getApplicationContext()
                try:
                    cr =  context.getContentResolver()
                    ws = None
                    if uri:
                        try:
                            ws  = cr.openOutputStream(uri,"rwt")
                        except:
                            Logger.info('File replace permission not granted.')
                            Logger.info('A new file version will be created.')
                            uri = None
                    if not ws:
                        cv = ContentValues()
                        cv.put(MediaStoreMediaColumns.DISPLAY_NAME, file_name)
                        cv.put(MediaStoreMediaColumns.RELATIVE_PATH, sub_directory)
                        root_uri = MediaStoreFiles.getContentUri('external')
                        uri = cr.insert(root_uri, cv)
                        ws  = cr.openOutputStream(uri)
                    # copy file contents
                    rs = FileInputStream(private_file)
                    FileUtils.copy(rs,ws) 
                    ws.flush()
                    ws.close()
                    rs.close()
                except Exception as e:
                    Logger.warning('SharedStorage.copy_to_shared():')
                    Logger.warning(str(e))
                    uri = None
                return uri
            else:
                root_directory = self._get_legacy_storage_location()
                if root_directory == None:
                    return None
                sub_directory = root_directory
                for d in path:
                    sub_directory = join(sub_directory,d) 
                    if not exists(sub_directory):
                        mkdir(sub_directory)
                public_path = join(sub_directory, file_name)
                self.delete_shared(public_path)
                copyfile(private_file, public_path)
                return public_path

        def _get_uri(self, shared_file):
            if type(shared_file) == str:
                shared_file = shared_file
                if 'file://' in shared_file or 'content://' in shared_file:
                    return None
            else:
                uri = cast('android.net.Uri',shared_file)
                try:
                    if uri.getScheme().lower() == 'content':
                        return uri
                    else:
                        return None
                except:
                    return None

            file_name = basename(shared_file) # "file1.txt"
            MIME_type = "text/plain" 
            path = shared_file.split('/')
            if len(path) < 1:
                return None
            root = path[0]
                
            self.selection = MediaStoreMediaColumns.DISPLAY_NAME+"=? AND " # "_display_name=? AND "
            if api_version > 28:
                location = ''
                for d in path[:-1]:
                    location = join(location,d)
                self.selection = self.selection +\
                    MediaStoreMediaColumns.RELATIVE_PATH+"=?" # "_display_name=? AND relative_path=?"
                self.args = [file_name, location+'/']
            else:
                self.selection = self.selection + MediaStoreMediaColumns.DATA+"=?"
                self.args = [file_name, shared_file]

            root_uri = self._get_root_uri(root, MIME_type) #returns uri of Documents folder
            context = mActivity.getApplicationContext()
            cursor = context.getContentResolver().query(root_uri, None,
                                                        self.selection,
                                                        self.args, None)
            fileUri = None
            if cursor:
                while cursor.moveToNext():
                    dn = MediaStoreMediaColumns.DISPLAY_NAME
                    index = cursor.getColumnIndex(dn)
                    fileName = cursor.getString(index)
                    if file_name == fileName:
                        id_index = cursor.getColumnIndex(MediaStoreMediaColumns._ID)
                        id = cursor.getLong(id_index)
                        fileUri = ContentUris.withAppendedId(root_uri,id)
                        break
                cursor.close()
            return fileUri

class MyPreview(Preview):
    screen = ObjectProperty()

    def on_touch_down(self, touch):
        if touch.is_double_tap:
            self.disconnect_camera()
            self.screen.close()
        else:
            return super().on_touch_down(touch) 
        
class CameraShootButton(ButtonBehavior, Label):

    def darker(self, color, factor=0.5):
        r, g, b, a = color
        r *= factor
        g *= factor
        b *= factor
        return r, g, b, a

class PictureMDScreen(MDScreen):
    tile = ObjectProperty()
    root = ObjectProperty()
    picture_name = StringProperty()
    photo_preview = ObjectProperty(None) # store the widget instance Preview
    source = StringProperty()
    if platform == "android":
        deviceOrientation = DeviceOrientation() # instance class to get orientation from java Listener
    orientation = StringProperty("6")
    clock_load_image = NumericProperty(0.2)
    torch = ObjectProperty()
    cache = BooleanProperty(True)

    def on_enter(self):
        self.photo_preview.connect_camera(filepath_callback= self.capture_path)
                                          
        if platform == "android":
            self.deviceOrientation.sensorEnable(True)

    def capture_path(self,file_path): ## called when clicking on the camera button
        '''
        if location not specified then the path will be : join(DCIM, app_name, subdir, name)
            and file will be saved to join(primary_external_storage_path(), DCIM, app_name, subdir, name).
            but error Permisson denied when we want to open it with Pillow at :
                -join(primary_external_storage_path(), DCIM, app_name, subdir, name)
                -file_path
            because app can't access to private data from internal storage, but can access to their 
            own private data...
                
        if location = "private" means /data/user/0/org.example.my_c4k/files/DCIM/ folder

        file_path = /data/user/0/org.example.my_c4k/files/DCIM/images/0.jpg with  my_c4k name of the app
        file_path is the location where the picture exists same as join(app_storage_path(), "DCIM", "images", self.picture_name+".jpg")
        destination = join(".","images", self.picture_name + ".png") # not working with os.rename maybe
        or because it is a relative path
        Environment.DIRECTORY_DCIM = "DCIM"

        root source listdir : ['app', 'DCIM'] # listdir(join(app_storage_path()))
        app source listdir : (root source + "app") : ['main.pyc', 'libpybundle.version', 'toast.pyc', 'camerax_provider', '.nomedia', 'android_permissions.pyc', '.kivy', 'p4a_env_vars.txt', '_python_bundle', 'sitecustomize.pyc', 'private.version']
        app source not showing folder images maybe because empty ? or because buildozer clean

        os.path.exists(file_path) : True

        cannot move image file_path path to join(app_storage_path(), "app", "images", self.picture_name + ".png")
        because os.rename only works if folder exist, here app/images does not exist

        if self.source = file_path, it seems that we can't load image from there so we need to move to 
        destination folder which is : join(app_storage_path(), "app", "images", self.picture_name + ".jpg")
        '''

        if platform in ["android","ios"]: 
            self.close() # we choose to close now so the waiting will be in home screen
            #move file from legacy storage (not secure) to app storage (secure)
            # We wanted to thread the disconnecting for performance, but unfortunately, doesn't work, so we decide 
            # to move it at beginning and performance is okay.
            self.disconnect_camera()
            destination = join(app_storage_path(), "app", "images", self.picture_name + ".jpg")
            self.source = destination

            try:
                # we use replace, not rename, because replace is cross-platform
                replace(file_path,destination) # move a file from source to destination 
                log("succeesss moving from DCIM to ./images")
            except FileNotFoundError:
                # there is no app folder so we create it,
                toast("creating the folder app for strorage purpose")
                mkdir(join(app_storage_path(), "app","images"))
                replace(file_path,destination)
                
            self.get_device_orientation()
            self.transpose_and_save()
            self.load_image()

            # save the picture to shared storage :
            private_storage = join("images", self.picture_name + ".jpg")
            # here save file has same source than destination because destination is tokenize and we get only the suffixe
            self.save_to_shared(private_storage,private_storage)
            

        elif platform in ["win","macos","linux","unknown"]: # for desktop tests
            self.source = join("images",self.picture_name + ".jpg")
            self.load_image()
            self.close()
            self.disconnect_camera()

    # on mainthread to avoid the two screen merging.
    @mainthread
    def close(self):
        self.root.current = 'home_screen' 
        if platform == "android":
            self.deviceOrientation.sensorEnable(False)
            self.torch.active = False

    def disconnect_camera(self):
        self.photo_preview.torch(state = "off")
        self.photo_preview.disconnect_camera()

    def get_device_orientation(self):
        # check if orientaton
        if not self.deviceOrientation.triumph:
            toast("no sensors availaible, default is portrait")
        else:
            # retrieve orientation from java sensors
            orientation = self.deviceOrientation.getOrientation()
            orientation = str(orientation)
            self.orientation = orientation
        
    # We add decorator because TypeError not in the mainThread, 
    # In general UI Changes needs to be done in mainthread

    @mainthread
    def load_image(self):
        self.tile.source = self.source
        self.tile.ids.image.reload() # reload image from cache

    def save_to_shared(self,source,destination):
        '''
        Here the saving process could be optimize with 
        a Chooser and a popup to enter the filename
        collection as argument seems not to be working, at contrario
        it saved the file without overriding it.
        copy_to_shared(source, collection = "Documents", destination)

        tries:
            copy_to_shared(source) # saves to Images/Appname
            copy_to_shared(source,collection = Environment.DIRECTORY_DOCUMENTS) # still saves to Images/Appname
            copy_to_shared(file_path, collection = Environment.DIRECTORY_DOCUMENTS, filepath=file_path) # if folder in file_path then it wil be created
        '''

        # Copy the filename to sharedstorage in "Documents/appnamefolder/folder1/filename"
        ss = MySharedStorage()
        ss.copy_to_shared(source, collection = Environment.DIRECTORY_DOCUMENTS, filepath=destination) # if folder in file_path then it wil be created
    
    def transpose_and_save(self):
        '''
        Image.FLIP_LEFT_RIGHT : rotate y axis (mirror the image)
        Image.ROTATE_90 or 180 or 270 same as Image.rotate() anticlockwise
        Image.TRANSPOSE = Image.FLIP_LEFT_RIGHT.ROTATE_90
        Even if transpose ROTATE_270 is faster (see plyer fonction), we choose rotate more flexible with angles
        code
        Warning, PIL .open or .save introduce a bug, which is the black line surrounder,
        But it's an easy fix thanks to expand=True
        '''
        if self.orientation != "1":
            # rotate and override image
            im = Image.open(self.source)
            if self.orientation == "6":  #"portrait"
                image_transposed = im.rotate(angle=270,expand=True)
            elif self.orientation == "3":  #"landscape-reverse"
                image_transposed = im.rotate(angle=180,expand=True)
            elif self.orientation == "8": # "portrait-reverse"
                image_transposed = im.rotate(angle=90,expand=True)

            image_transposed.save(self.source) # replace image

    def app_name(self):
        context = mActivity.getApplicationContext()
        appinfo = context.getApplicationInfo()
        if appinfo.labelRes:
            name = context.getString(appinfo.labelRes)
        else:
            name = appinfo.nonLocalizedLabel.toString()
        return name

class MyMDSmartTile(MDSmartTile):
    text = StringProperty()

class MyMDScreenManager(MDScreenManager): 

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):

        #Create the tiles
        for i in range(10):
            self.ids._mybox.add_widget(MyMDSmartTile(text = str(i)))

class DeviceOrientation(MDApp):
    def build(self):
        return Builder.load_string(KV)

    def on_start(self):
        self.dont_gc = AndroidPermissions(self.start_app)

    def start_app(self):
        self.dont_gc = None

    def on_stop(self):
        # make sure Sensor is disconnected:
        if platform == "android":
            self.root.ids._picture_screen.deviceOrientation.sensorEnable(False)

if __name__ == "__main__":
    DeviceOrientation().run()


