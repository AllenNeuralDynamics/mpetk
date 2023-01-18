#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import os
import pprint
import sys

import kazoo
import mpeconfig
import yaml
from yaml import representer

yaml.add_representer(dict, lambda self, data: yaml.representer.SafeRepresenter.represent_dict(self, data.items()))


def delete(server, path):
    """
    Delete a path from the server.
    :param server: zk server
    :param path: path to delete
    :return:
    """
    server.delete(path, recursive=True)


def push(server, path, file, serialization="yaml"):
    """
    Store a yaml coniguration to the server
    :param server: zk server
    :param path: path to store data
    :param file: yaml file to upload
    :param serialization: a serialization method [default = 'yaml']
    :return:
    """
    if os.path.isfile(file):
        with open(file, "r") as f:
            data = f.read()
            server[path] = data.encode()
            # logging.admin(f"A new configuration was pushed for {path}", extra={"weblog": True})
    else:
        print(f"{file} is not a valid file.")


def pull(server, path, file, serialization="yaml"):
    """
    pull a yaml configuration from the server
    :param server: zk server
    :param path: path to pull data from
    :param file: optional file to save configuration
    :param serialization: serialization method [default = 'yaml']
    :return: yaml data
    """
    if path.startswith("//"):
        path = path[1:]
    print("pulling from", path)
    data = yaml.safe_load(server[path])
    if file:
        with open(file, "w") as f:
            yaml.dump(data, f, default_flow_style=False)
    return data


def move_copy(server, from_path, to_path, do_move=True, recursive=False):
    """
    Move or Copy a configuration from one path to another.
    :param server: zk server
    :param from_path: source path
    :param to_path: target path
    :param do_move: True = move, False = copy
    :param recursive: copy subdirectories as well [default = false]
    :return:
    """
    server[to_path] = server[from_path]
    if not recursive:
        if do_move:
            server.delete(from_path)
        return

    for p in server.get_children(from_path):
        if server[f"{from_path}/{p}"]:
            server[f"{to_path}/{p}"] = server[f"{from_path}/{p}"]
        move_copy(server, f"{from_path}/{p}", f"{to_path}/{p}", do_move, recursive)

        if server.get_children(f"{from_path}/{p}") and do_move:
            server.delete(f"{from_path}/{p}")
    server.delete(f"{from_path}")


def list_children(server, path, recursive=False, indent=0):
    """
    Fetch the list of children to the screen.
    :param server: zk server
    :param path: root path to read
    :param recursive: print subdirectories [default = false]
    :param indent: indention preference [default = 0]
    :return: children of path
    """
    if not recursive:
        return server.get_children(path)

    for p in server.get_children(path):
        if p == "zookeeper":
            continue

        asterisk = "*" if server[f"{path}/{p}"] else ""
        print(f"{'  |' * indent}{'-' * min(indent, 1)}{p}{asterisk}")

        list_children(server, f"{path}/{p}", recursive=True, indent=indent + 1)
        if indent == 0:
            print()


def dump_to_dir(server, path, recursive=False, indent=0):
    dump_file = path.replace("/", "__")
    try:
        pull(server, path[1:], dump_file, serialization="yaml")
    except Exception as err:
        print(err)
        print("ignoring", path)

    for p in server.get_children(path):
        if p == "zookeeper":
            continue
        dump_to_dir(server, f"{path}/{p}", recursive=True, indent=indent + 1)


def load_from_dir(server):
    import glob

    files = glob.glob("____*")
    for file_ in files:
        y = yaml.safe_load(open(file_, "r"))
        if y:
            path = file_.replace("__", "/")
            push(server, path, file_)


def create(server, path):
    """
    Creates a path with no data on the server.
    :param server: zk zerver
    :param path: path to create
    :return:
    """
    server[path] = None


def main():
    mpeconfig.source_configuration("mpeconfig", send_start_log=False)

    parser = argparse.ArgumentParser(
        description="""command line tools for the MPE configuration server.""",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("command", choices=["load", "dump", "push", "pull", "list", "delete", "move", "copy", "create"])
    parser.add_argument("path", help="the zookeeper path to operate on")
    parser.add_argument(
        "file", nargs="?", help="file or path of a config, or the copy location for move and copy", default=None
    )
    parser.add_argument(
        "-r", "--recursive", action="store_true", help="determines whether to list, copy and delete recursively"
    )
    parser.add_argument("--hosts", default=["aibspi:2181"], help="a list of zookeeper hosts:  aibspi:2181,aibspi2:1234")

    args = parser.parse_args(sys.argv[1:])

    server = mpeconfig.ConfigServer(hosts=args.hosts)
    server.start()
    if args.command == "dump":
        dump_to_dir(server, "/", True)
    if args.command == "load":
        load_from_dir(server)

    elif args.command == "pull":
        result = pull(server, args.path, args.file)
        if result:
            pprint.pprint(result)

    elif args.command == "list":
        try:
            if args.recursive:
                print("\nhost:", server.hosts)
                print("-" * len(f"host: {server.hosts}"))
            result = list_children(server, args.path, args.recursive)
            if result:
                print(result)
        except kazoo.exceptions.NoNodeError:
            print(f"Could not find {args.path} on server.")
            return 1

    elif args.command == "push":
        push(server, args.path, args.file)

    elif args.command == "delete":
        delete(server, args.path)

    elif args.command == "copy":
        move_copy(server, args.path, args.file, do_move=False, recursive=args.recursive)

    elif args.command == "move":
        move_copy(server, args.path, args.file, do_move=True, recursive=args.recursive)

    elif args.command == "create":
        create(server, args.path)

    else:
        parser.parse_args(["-h"])
    server.stop()


if __name__ == "__main__":
    main()
