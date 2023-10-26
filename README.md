# What this repo does ?
Goal to this repo :
Make an android app with Kivy, that takes a picture from the 4 orientations which are
    ["portrait","landscape","reverse-portrait","reverse-landscape"]
and display the picture in the correct orientation even when the orientation in buildozer.spec is constant and set to "portrait"

# Requirements
All requirements are in buildozer.spec file, so if you want to test it before on computer,
you'll need to pip install :  
  kivy==master,
  https://github.com/kivymd/KivyMD/archive/master.zip,
  pillow,
  camera4kivy,
  gestures4kivy,
  androidstorage4kivy

Otherwise, for android, Buildozer will do it for you.

camera4kivy is needed to use the camera provider and preview Widget, we add just the DeviceOrientation class to get Orientation device in real time

androidstorage4kivy is used here to save the pictures to a permanent storage (not deleted after app is uninstalled)
So after testing, don't forget to delete the images that are also saved to your android storage Documents/myapp/images folder

# Cross Platform
Never tested in IOS, tested in Android 10 api 29.

# How to test it
Once the app installed and working, you should see a 10 Tiles with camera's icons in each of them, choose one and click on the small camera icon this open a new screen with the Preview Widget, there you can either click on the blue camera icon to take a picture or tap 2 times to exit the screen and choose not to take the picture.
You can also test the flash, the torch etc...
When taking the picture, the picture is loaded in the Tile and also saved to the android shared storage ("Documents/appname/images").
When dealing with pictures we often want to save them to a persistant storage, if you save it to the app private storage it will be deleted when the app is uninstall.

# Limits to this script

Sometimes the picture is not retrieved to the correct orientation, this is maybe because the sensor is not working as it should
this is on android, so we cannot fix it easily. This happends rarely, and you just have to take again the picture, and should be ok.
Another limit is that sometimes the pictures is saved with "Picture1 (01).jpg", "Picture1 (02).jpg", suffixe (01) is added by android, why ?
We don't know...
