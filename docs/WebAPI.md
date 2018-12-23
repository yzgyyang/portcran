# Portd WebAPI
The following resources are available:
 - `/ports`: ports manageable through Portd
 - `/patches`: list of open patches against the FreeBSD Ports Collection

## `/ports`
The list of ports manageable through Portd.  The correctly supported ports are based on:
 - CRAN: Core R Archive Network
 - PIP: Python Independent Packages (???)

Ports from the above sources can be created, updated and removed.  If a port has a missing dependency this can
also be created.

A port looks as follows:
```json
{
    "name": "$PORTNAME",
    "version": "$DISTVERSION",
    "maintainer": "$MAINTAINER",
    "source": /*one of "cran", "pip"*/,
    "latest_version": /*latest version available at source*/,
    "origin": /*directory location of port*/,
    "patch": /*URI to patch against this port (if any)*/,
}
```

The properties that can be updated are:
 - `source`: If set to `latest` then the latest version from the port source will be used.  Otherwise the port will be
   updated to the specified version.
 - `maintainer`: The maintainer can either be assinged to `ports@FreeBSD.org` (if not already that user), or to a
   specified maintainer if the current maintainer is `ports@FreeBSD.org`.

## `/patches`
The list of open patches against the FreeBSD Ports Collection.  To create a patch perform the relevant action on the
underlying port.  The patch URI will then appear in the port's `patch` property.

A patch looks as follows:
```json
{
    "uri": /*URI of this patch*/,
    "port": /*URI of the Port this patch is against*/,
    "action": /*one of "create", "update", "remove"*/,
    "log": /*commmit message of the patch*/,
    "status": /*one of "generate", "lint", "build", "wait", "commit", "error"*/,
    "error": /*if in "status":"error" then a description of the error message*/,
    "diff": /*URI of the actual patch*/,
    "poudriere": {
        /*URI of build log*/: {
            "arch": /*build architecture*/,
            "version": /*version of FreeBSD*/,
        },
    },
    "dependencies": [
        /* URI to dependant patch*/
    ]
}
```

The properties than can be updated are:
 - `log`: change the commit log message.
 - `status`: if the current status is `wait` then the status can be changed to `commit` if the patch is approved.
