# Changelog
## 0.5.0 (2023-08-17)
* teamstk now added
* rewrites to mpeconfig

## 0.4.6 (2023-08-08)

## 0.4.6.dev3 (2023-08-08)

## 0.4.6.dev2 (2023-05-22)
* Updated the requirements.txt.  It removes a lot of cruft and is more permissive to pyzmq in particular

## 0.4.6.dev1 (2023-03-31)
* Fixed "no module named zro" in RemoteObject
* Replaced deprecated time.clock() with time.perf_counter()
## 0.4.6.dev0 (2023-03-31)
## 0.4.5.dev0 (2023-03-31)
## 0.4.4 (2023-03-31)
## 0.4.4.dev3 (2023-02-28)
## 0.4.4.dev2 (2023-02-27)
## 0.4.4.dev1 (2023-01-18)
* src moved to mpetk for setup.py

## 0.4.4.dev0 (2023-01-17)
* session.Session.write_manifest will now log that it wrote a manifest.

## 0.4.3 (2022-12-12)
* changed mpeconfig to host the yml files internally instead of as external files

## 0.4.2 (2022-12-12)
* Changed build.py to "include_file" instead of "install_file" on no code files.  Important because the manifest that is generated has breaking syntax on "install_file" for linux.

## 0.4.1 (2022-07-15)
* removed auto-detection of version

## 0.4.0 (2022-07-14)
* added mtrain toolkit

## 0.3.6 (2022-05-10)

* control-c will call exit()

## 0.3.5 (2021-10-13)

* fixed lims dynamic functions bug

## 0.3.2 (2021-09-27)

* Updated broken requirement for pyyaml
* Removed python2 mpeconfig version as it is no longere supported

## 0.3.1 (2021-07-26)

* fixed pyzmq bug with pyinstaller by downgrading to 19.0.2 (still 3.9.5 compat)

## 0.3.0 (2021-07-23)
* bumped to production

## 0.3.0.dev2 (2021-07-22)
* fixed info logging
* removed errant print

## 0.3.0.dev1 (2021-07-22)

* added file-based ipc
* added comma

## 0.3.0.dev0 (2021-07-14)
* added initial support for serialization methods

## 0.2.0.dev3 (2021-05-12)

* Removed need for QT Framework

## 0.2.0.dev2 (2021-05-06)

* updated build.py to include data_files as well as package_data

## 0.2.0.dev1 (2021-04-20)

* updated build.py

## 0.2.0.dev0 (2021-04-20)

* initial build
