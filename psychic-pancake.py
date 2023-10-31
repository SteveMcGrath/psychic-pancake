#!/usr/bin/env python
"""
Psychic Pancake Cloudflare Image Uploader
"""
from typing import Optional, List, Tuple
from pathlib import Path
from csv import DictWriter
import logging
from PIL import Image
import typer


__author__ = 'Lickitysplitted'
__version__ = '0.0.1'


app = typer.Typer()
logger = logging.getLogger(__name__)


def image_checker(path: Path,
                  max_bytes: int = 10485760,
                  max_dim: int = 12000,
                  max_pixels: int = 100000000,
                  image_types: List[str] = ['PNG', 'JPEG']
                  ) -> bool:
    """
    Checks to see that the image is is valid and conforms to the restrictions
    set by Cloudflare.

    Args:
        path (Path): The path to the image file.
        max_bytes (int, optional):
            The maximum size of the image in bytes.  The default is the
            Cloudflare specified max.
        max_dim (int, optional):
            The maximum size (width or height) in pixels that the image may be.
            The default comes from the Cloudflare documentation.
        max_pixels (int, optional):
            The maximum number of pixels that the image can possess.  The
            default comes from the Cloudflare documentation.
        image_types (List[str], optional):
            The supported filetypes for uploading.

    Returns:
        bool:
            Does the file specified pass all of the checks?
    """
    # if no path is specified, then we should bail right away.
    if not path:
        return False

    # Attempt to open the file as an image.  If this fails we will then log
    # the exception and return a false to the caller.
    try:
        img = Image.open(path)
    except Exception as exc:
        logger.exception(exc)
        return False

    # Check to see if the file is a supported filetype.  If not, then log the
    # warning and return a false to the caller.
    if img.format not in image_types:
        logger.warn(f'CHECK-FAIL: {path} is an unsupported file')
        return False

    # Check to see if the file is under the maximum byte size.  If it's not we
    # will then log the warning and return a false to the caller.
    if path.stat().st_size > max_bytes:
        logger.warn(f'CHECK-FAIL: {path} exceeds max size')
        return False

    # Check to see if the image exceeds the maximum number of pixels supported.
    # If it does exceed the max pixel count, then we will log a warning and
    # return false to the caller.
    if (img.width * img.height) > max_pixels:
        logger.warn(f'CHECK-FAIL: {path} exceeds max pixel count')
        return False

    # Check to see if the image exceed the maximal size in either dimension for
    # the the image.  If it does, then log the warning and return false to
    # the caller.
    if image.width > max_dim or image.height > max_dim:
        logger.warn(f'CHECK-FAIL: {path} exceeds dimensional limits')
        return False

    # if we pass all the checks for the file, then return True.
    return True


def upload_to_cloudflare(image: Path, cf_id: str, cf_token: str) -> dict:
    """
    Uploads the image to Cloudflare, then captures and returns the response.

    Args:
        image (Path): The image path.
        cf_id (str): The Cloudflare customer id.
        cf_token (str): The Cloudflare authorization token.

    Returns:
        dict:
            The JSON response from Cloudflare.
    """

    # Upload the image to the Cloudflare account
    url = f'https://api.Cloudflare.com/client/v4/accounts/{cfid}/images/v1'
    resp = requests.post(url=url,
                         headers={'Authorization': f'Bearer {cf_token}'},
                         files={'file': (image.stem, image.open('rb'))}
                         )

    # If the status-code isn't 200, then we need to log that the error had
    # occured and return a NoneType to the caller.
    if resp.status_code != 200:
        logger.error(
            (f'The upload of {image} to Cloudflare has failed with '
             f'a status code of {resp.status_code}.')
        )
        return None

    # Check to see if the response from Cloudflare says that the image was
    # successfully uploaded.  If it wasn't then we need to log the error
    # and return a NoneType
    ret = resp.json()
    if ret.get('success') != 'true':
        logger.error(
            (f'The upload of {image} to Cloudflare has failed with an '
             f'unknown error and response of {ret}')
        )
        return None

    # As everything seems to upload normally, return the json body.
    return ret


def file_walker(pobj: Path,
                cf_id: str,
                cf_token: str
                ) -> List[Tuple[str, dict]]:
    """
    Recursive Directory walker && File uploader

    Args:
        pobj (Path): The base path to walk & upload
        cf_id (str): Cloudflare id to pass to the uploader
        cf_token (str): Cloudflare authorization token to pass to the uploader

    Returns:
        List[Tuple[str, dict]]]:
            List up response tuples from the uploader.
    """
    file_log = []

    # If the path object is a directory, we will then iterate over the path and
    # call ourselves again with each object returned.  We will then merge the
    # results from the recursive calls back into our own file log.
    if pobj and pobj.is_dir():
        for item in pobj.iterdir():
            file_log += file_walker(pobj=item, cf_id=cf_id, cf_token=cf_token)

    # If the path object if a file, we'll first ensure that it is an image and
    # that it matches the requirements of the Cloudflare API.  If so, then
    # we'll upload the file and append the path object and the response to the
    # file_log.
    elif pobj.is_file() and image_checker(pobj):
        resp = upload_to_cloudflare(image=pobj, cf_id=cf_id, cf_token=cf_token)
        logger.info(f'Successfully uploaded {pobj}: {resp}')
        file_log.append((pobj, resp))

    # Return the file_log to the caller.
    return file_log


@app.command()
def uploader(path: Path,
             cloudflare_token: str = typer.Option(
                help='Cloudflare authorization token',
                envvar='CLOUDFLARE_AUTH_TOKEN',
             ),
             cloudflare_id: str = typer.Option(
                help='Cloudflare id',
                envvar='CLOUDFLARE_ID'
             ),
             report: Optional[Path] = typer.Option(None,
                help='CSV report filename',
             ),
             verbose: int = typer.Option(0,
                help='Log verbosity level'
                '--verbose', '-v',
                count=True,
                max=4
            ),
            ):
    """
    Psychic Pancake Cloudflare image uploader
    """
    # Set the logging level.
    logging.basicConfig(level=(verbose * 10) - 40)

    # Walk the path specified and attempt to upload any files within it.
    file_log = file_walker(pobj=path,
                           cf_id=cloudflare_id,
                           cf_token=cloudflare_token
                           )

    # If a report file was defined, then we will write the responses to it.
    if report:
        with open(report, 'w', encoding='utf-8') as robj:
            writer = DictWriter(robj, ['filename', 'id', 'upload', 'varients'])
            writer.writeheader()
            for entry in file_log:
                writer.writerow({
                    'filename': str(entry[0].resolve()),
                    'id': entry[1].get('id'),
                    'upload': entry[1].get('uploaded'),
                    'varients': entry[1].get('varients'),
                })


if __name__ == '__main__':
    app()
