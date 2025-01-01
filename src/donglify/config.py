import sys
import configparser
import pathlib

from pydantic import BaseModel, TypeAdapter, ValidationError

from abc import ABC, abstractmethod

from donglify.lib import *

class DongleInstall(BaseModel, extra="forbid"):
    kernel_name: str
    kernel_args: str
    kernel_version: str
    cryptokeyfile: str
    hooks_added: str
    ucode: str

DongleInstallValidator = TypeAdapter(DongleInstall)

class DongleISO(BaseModel, extra="forbid"):
    file_name: str
    loopback_cfg_location: str

DongleISOValidator = TypeAdapter(DongleISO)

class DongleDesc(BaseModel, extra="forbid"):
    version: str
    efi_uuid: str
    locked_boot_uuid: str
    unlocked_boot_uuid: str
    part_iso_uuid: str

DongleConfigValidator = TypeAdapter(DongleDesc)

class DonglifyConfigV(ABC, BaseModel, extra="forbid"):
    @staticmethod
    @abstractmethod
    def convert_to_version(data):
        pass

class DonglifyConfigV1(DonglifyConfigV):
    config: DongleDesc
    installs: dict[str, DongleInstall]

    isos: dict[str, DongleISO]

    @staticmethod
    def convert_to_version(data):
        # add version field in data["config"]
        data["config"]["version"] = "1"
        tell("added version field to dongle.ini")

        # remove name from installs
        for name, install in data["installs"].items():
            install.pop("name")
            tell(f"removed no longer required name field, {name}, from installs")

        return data

DongleConfigV1Validator = TypeAdapter(DonglifyConfigV1)

class DonglifyState:
    LATEST_VERSION = "1"
    @classmethod
    def init(cls, data):
        try:
            cls.validate(data)
            cls.ask_user_to_accept_config()
        except Exception as e1:
            try:
                tell("attempting to convert dongle.ini to v1")
                data = DonglifyConfigV1.convert_to_version(data)
                cls.validate(data)
                good("dongle.ini has been converted to v1, manual verification is always recommended")
                cls.ask_user_to_accept_config()
                print("Would you like to save this configuration?")
                if does_user_accept():
                    cls.write()
                    good("dongle.ini has been saved")
            except Exception as _:
                bad("could not convert dongle.ini to latest version")
                bad("please fix dongle.ini manually and try again")
                bad(f"Validation Exception: {e1}")
                sys.exit(1)
        
    @classmethod
    def validate(cls, data):
        try:
            state = DongleConfigV1Validator.validate_python(data, strict=True)

            cls.config = state.config
            cls.installs = state.installs
            cls.isos = state.isos
        except ValidationError as e:
            bad("dongle.ini is not valid: ")
            for error in e.errors():
                loc = ""
                for l in error["loc"]:
                    loc += l.__str__() + "."
                loc = loc[:-1]
                bad(f" - Field: {loc} = {error["input"]}, {error["type"]}: {error["msg"]},")
            raise Exception("Invalid dongle.ini")

    @abstractmethod 
    def ask_user_to_accept_config():
        print(colored("Please review that this dongle.ini is correct:", "yellow"))
        parser = DonglifyState.create_parser()
        parser.write(sys.stdout, space_around_delimiters=True)

        print("Looks good?")
        if not does_user_accept():
            bad("dongle.ini has been rejected by user command.")
            sys.exit(1)

    @abstractmethod
    def read():
        parser = configparser.ConfigParser()
        try:
            parser.read("/boot/dongle.ini")
            if not parser.sections():
                bad("dongle.ini is empty")
                sys.exit(1)
        except Exception as e:
            bad("Error reading dongle.ini")
            print(e)
            sys.exit(1)
        try:
            data = {"isos": {}, "installs": {}}
            for name in parser.sections():
                if name == "dongle":
                    data["config"] = dict(parser[name].items())
                elif "iso." in name:
                    data["isos"][name.split(".")[1]] = dict(parser[name].items())
                else:
                    data["installs"][name] = dict(parser[name].items())
    
            DonglifyState.init(data)

        except Exception as e:
            bad("Error parsing dongle.ini")
            print(e)
            sys.exit(1)

    @classmethod
    def create_parser(cls) -> configparser.ConfigParser:
        parser = configparser.ConfigParser()
        parser.read_dict({"dongle": cls.config.model_dump()})

        for name, install in DonglifyState.installs.items():
            parser.read_dict({name: install.model_dump()})

        for name, iso in DonglifyState.isos.items():
            parser.read_dict({"iso." + name: iso.model_dump()})

        return parser

    @classmethod
    def write(cls):
        parser = cls.create_parser()
        with open("/boot/dongle.ini", 'w') as f:
            parser.write(f, space_around_delimiters=True)

        os.chmod("/boot/dongle.ini", 600)

    @classmethod
    def locate_and_load_config(cls, dev_name):
        tell("attempting to locate dongle.ini")
    
        unlock_disk(dev_name, "dongleboot")
        mount_mapper("dongleboot", "/boot")
    
        if not pathlib.Path("/boot/dongle.ini").exists():
            bad("/boot/dongle.ini does not exist, choose another device partition or run dongle init")
            sys.exit(1)
    
        cls.read()
