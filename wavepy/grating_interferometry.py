#!/usr/bin/env python
# -*- coding: utf-8 -*-
# #########################################################################
# Copyright (c) 2015, UChicago Argonne, LLC. All rights reserved.         #
#                                                                         #
# Copyright 2015. UChicago Argonne, LLC. This software was produced       #
# under U.S. Government contract DE-AC02-06CH11357 for Argonne National   #
# Laboratory (ANL), which is operated by UChicago Argonne, LLC for the    #
# U.S. Department of Energy. The U.S. Government has rights to use,       #
# reproduce, and distribute this software.  NEITHER THE GOVERNMENT NOR    #
# UChicago Argonne, LLC MAKES ANY WARRANTY, EXPRESS OR IMPLIED, OR        #
# ASSUMES ANY LIABILITY FOR THE USE OF THIS SOFTWARE.  If software is     #
# modified to produce derivative works, such modified software should     #
# be clearly marked, so as not to confuse it with the version available   #
# from ANL.                                                               #
#                                                                         #
# Additionally, redistribution and use in source and binary forms, with   #
# or without modification, are permitted provided that the following      #
# conditions are met:                                                     #
#                                                                         #
#     * Redistributions of source code must retain the above copyright    #
#       notice, this list of conditions and the following disclaimer.     #
#                                                                         #
#     * Redistributions in binary form must reproduce the above copyright #
#       notice, this list of conditions and the following disclaimer in   #
#       the documentation and/or other materials provided with the        #
#       distribution.                                                     #
#                                                                         #
#     * Neither the name of UChicago Argonne, LLC, Argonne National       #
#       Laboratory, ANL, the U.S. Government, nor the names of its        #
#       contributors may be used to endorse or promote products derived   #
#       from this software without specific prior written permission.     #
#                                                                         #
# THIS SOFTWARE IS PROVIDED BY UChicago Argonne, LLC AND CONTRIBUTORS     #
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT       #
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS       #
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL UChicago     #
# Argonne, LLC OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,        #
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,    #
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;        #
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER        #
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT      #
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN       #
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE         #
# POSSIBILITY OF SUCH DAMAGE.                                             #
# #########################################################################


"""


Grating interferometry
----------------------


This library contain the function to analyse data from grating
interferometry experiments.

There are several different layouts for a grating interferometry experiments,
where one could use: one dimensional, two-dimensional (checked board) or
circular gratings; phase or absorption gratings; and, in experimetns with more
than one grating, we can have combination of different gratings.

For this reason, it is very difficult to write a function that covers all the
possibilities and (at least initally) we need a function for each particular
case.




"""

# import itertools
# import numpy as np
# import time
# from tqdm import tqdm
#
# from skimage.feature import register_translation
#
# from multiprocessing import Pool, cpu_count
#
# import wavepy.utils as wpu
#
# from wavepy.cfg import *


import numpy as np
import matplotlib.pyplot as plt
import wavepy.utils as wpu

from skimage.restoration import unwrap_phase


import unwrap as uw


__authors__ = "Walan Grizolli"
__copyright__ = "Copyright (c) 2016, Affiliation"
__version__ = "0.1.0"
__docformat__ = "restructuredtext en"
__all__ = ['exp_harm_period', 'extract_harmonic',
           'plot_harmonic_grid', 'plot_harmonic_peak',
           'single_grating_harmonic_images', 'single_2Dgrating_analyses',
           'visib_1st_harmonics']


def _idxPeak_ij(harV, harH, nRows, nColumns, periodVert, periodHor):
    """
    Calculates the indexes of the peak of the harmonic harV, harH in the main
    FFT image
    """
    return [nRows // 2 + harV * periodVert, nColumns // 2 + harH * periodHor]


def _idxPeak_ij_exp(imgFFT, harV, harH, periodVert, periodHor, searchRegion):
    """
    Returns the index of the maximum intensity in a harmonic sub image.
    """

    intensity = (np.abs(imgFFT))

    (nRows, nColumns) = imgFFT.shape

    idxPeak_ij = _idxPeak_ij(harV, harH, nRows, nColumns,
                             periodVert, periodHor)

    maskSearchRegion = np.zeros((nRows, nColumns))

    maskSearchRegion[idxPeak_ij[0] - searchRegion:
                     idxPeak_ij[0] + searchRegion,
                     idxPeak_ij[1] - searchRegion:
                     idxPeak_ij[1] + searchRegion] = 1.0

    idxPeak_ij_exp = np.where(intensity * maskSearchRegion ==
                              np.max(intensity * maskSearchRegion))

    return [idxPeak_ij_exp[0][0], idxPeak_ij_exp[1][0]]


def _check_harmonic_inside_image(harV, harH, nRows, nColumns,
                                 periodVert, periodHor):
    """
    Check if full harmonic image is within the main image
    """

    errFlag = False

    if (harV + .5)*periodVert > nRows / 2:
        wpu.print_red("ATTENTION: Harmonic Peak " +
                      "{:d}{:d}".format(harV, harH) +
                      " is out of image vertical range.")
        errFlag = True

    if (harH + .5)*periodHor > nColumns / 2:
        wpu.print_red("ATTENTION: Harmonic Peak " +
                      "{:d}{:d} is ".format(harV, harH) +
                      "is out of image horizontal range.")
        errFlag = True

    if errFlag:
        raise ValueError("ERROR: Harmonic Peak " +
                         "{:d}{:d} is ".format(harV, harH) +
                         "out of image frequency range.")


def _error_harmonic_peak(imgFFT, harV, harH,
                         periodVert, periodHor, searchRegion=10):
    """
    Error in pixels (in the reciprocal space) between the harmonic peak and
    the provided theoretical value
    """

    (nRows, nColumns) = imgFFT.shape

    #  Estimate harmonic positions

    idxPeak_ij = _idxPeak_ij(harV, harH, imgFFT.shape[0], imgFFT.shape[1],
                             periodVert, periodHor)

    idxPeak_ij_exp = _idxPeak_ij_exp(imgFFT, harV, harH,
                                     periodVert, periodHor, searchRegion)

    del_i = idxPeak_ij_exp[0] - idxPeak_ij[0]
    del_j = idxPeak_ij_exp[1] - idxPeak_ij[1]

    return del_i, del_j


def exp_harm_period(img, harmonicPeriod,
                    harmonic_ij='00', searchRegion=10,
                    isFFT=False, verbose=True):
    """
    Function to obtain the position (in pixels) in the reciprocal space
    of the first harmonic ().
    """

    (nRows, nColumns) = img.shape

    harV = int(harmonic_ij[0])
    harH = int(harmonic_ij[1])

    periodVert = harmonicPeriod[0]
    periodHor = harmonicPeriod[1]

    # adjusts for 1D grating
    if periodVert <= 0 or periodVert is None:
        periodVert = nRows
        if verbose:
            wpu.print_blue("MESSAGE: Assuming Horizontal 1D Grating")

    if periodHor <= 0 or periodHor is None:
        periodHor = nColumns
        if verbose:
            wpu.print_blue("MESSAGE: Assuming Vertical 1D Grating")

    _check_harmonic_inside_image(harV, harH, nRows, nColumns,
                                 periodVert, periodHor)

    if isFFT:
        imgFFT = img
    else:
        imgFFT = np.fft.fftshift(np.fft.fft2(img, norm='ortho'))

    del_i, del_j = _error_harmonic_peak(imgFFT, harV, harH,
                                        periodVert, periodHor,
                                        searchRegion)

    if verbose:
        wpu.print_blue("MESSAGE: error experimental harmonics " +
                       "vertical: {:d}".format(del_i))
        wpu.print_blue("MESSAGE: error experimental harmonics " +
                       "horizontal: {:d}".format(del_j))

    return periodVert + del_i, periodHor + del_j


def extract_harmonic(img, harmonicPeriod,
                     harmonic_ij='00', searchRegion=10, isFFT=False,
                     plotFlag=False, verbose=True):

    """
    Function to extract one harmonic image of the FFT of single grating
    Talbot imaging.


    The function use the provided value of period to search for the harmonics
    peak. The search is done in a rectangle of size
    ``periodVert*periodHor/searchRegion**2``. The final result is a rectagle of
    size ``periodVert x periodHor`` centered at
    ``(harmonic_Vertical*periodVert x harmonic_Horizontal*periodHor)``


    Parameters
    ----------

    img : 	ndarray – Data (data_exchange format)
        Experimental image, whith proper blank image, crop and rotation already
        applied.

    harmonicPeriod : list of integers in the format [periodVert, periodHor]
        ``periodVert`` and ``periodVert`` are the period of the harmonics in
        the reciprocal space in pixels. For the checked board grating,
        periodVert = sqrt(2) * pixel Size / grating Period * number of
        rows in the image. For 1D grating, set one of the values to negative or
        zero (it will set the period to number of rows or colunms).

    harmonic_ij : string or list of string
        string with the harmonic to extract, for instance '00', '01', '10'
        or '11'. In this notation negative harmonics are not allowed.

        Alternativelly, it accepts a list of string
        ``harmonic_ij=[harmonic_Vertical, harmonic_Horizontal]``, for instance
        ``harmonic_ij=['0', '-1']``

        Note that since the original image contain only real numbers (not
        complex), then negative and positive harmonics are symetric
        related to zero.
    isFFT : Boolean
        Flag that tells if the input image ``img`` is in the reciprocal
        (``isFFT=True``) or in the real space (``isFFT=False``)

    searchRegion: int
        search for the peak will be in a region of harmonicPeriod/searchRegion
        around the theoretical peak position

    plotFlag: Boolean
        Flag to plot the image in the reciprocal space and to show the position
        of the found peaked and the limits of the harmonic image

    verbose: Boolean
        verbose flag.


    Returns
    -------
    2D ndarray
        Copped Images of the harmonics ij


    This functions crops a rectagle of size ``periodVert x periodHor`` centered
    at ``(harmonic_Vertical*periodVert x harmonic_Horizontal*periodHor)`` from
    the provided FFT image.


    Note
    ----
        * Note that it is the FFT of the image that is required.
        * The search for the peak is only used to print warning messages.

    **Q: Why not the real image??**

    **A:** Because FFT can be time consuming. If we use the real image, it will
    be necessary to run FFT for each harmonic. It is encourage to wrap this
    function within a function that do the FFT, extract the harmonics, and
    return the real space harmonic image.


    See Also
    --------
    :py:func:`wavepy.grating_interferometry.plot_harmonic_grid`

    """

    (nRows, nColumns) = img.shape

    harV = int(harmonic_ij[0])
    harH = int(harmonic_ij[1])

    periodVert = harmonicPeriod[0]
    periodHor = harmonicPeriod[1]

    if verbose:
            wpu.print_blue("MESSAGE: Extracting harmonic " +
                           harmonic_ij[0] + harmonic_ij[1])
            wpu.print_blue("MESSAGE: Harmonic period " +
                           "Horizontal: {:d} pixels".format(periodHor))
            wpu.print_blue("MESSAGE: Harmonic period " +
                           "Vertical: {:d} pixels".format(periodVert))

    # adjusts for 1D grating
    if periodVert <= 0 or periodVert is None:
        periodVert = nRows
        if verbose:
            wpu.print_blue("MESSAGE: Assuming Horizontal 1D Grating")

    if periodHor <= 0 or periodHor is None:
        periodHor = nColumns
        if verbose:
            wpu.print_blue("MESSAGE: Assuming Vertical 1D Grating")

    try:
        _check_harmonic_inside_image(harV, harH, nRows, nColumns,
                                     periodVert, periodHor)
    except ValueError:
        raise SystemExit

    if isFFT:
        imgFFT = img
    else:
        imgFFT = np.fft.fftshift(np.fft.fft2(img, norm='ortho'))

    intensity = (np.abs(imgFFT))

    #  Estimate harmonic positions
    idxPeak_ij = _idxPeak_ij(harV, harH, nRows, nColumns,
                             periodVert, periodHor)

    del_i, del_j = _error_harmonic_peak(imgFFT, harV, harH,
                                        periodVert, periodHor,
                                        searchRegion)

    if verbose:
        print("MESSAGE: extract_harmonic:" +
              " harmonic peak " + harmonic_ij[0] + harmonic_ij[1] +
              " is misplaced by:")
        print("MESSAGE: {:d} pixels in vertical, {:d} pixels in hor".format(
               del_i, del_j))

        print("MESSAGE: Theoretical peak index: {:d},{:d} [VxH]".format(
              idxPeak_ij[0], idxPeak_ij[1]))

    if ((np.abs(del_i) > searchRegion // 2) or
       (np.abs(del_j) >  searchRegion // 2)):

        wpu.print_red("ATTENTION: Harmonic Peak " + harmonic_ij[0] +
                      harmonic_ij[1] + " is too far from theoretical value.")
        wpu.print_red("ATTENTION: {:d} pixels in vertical,".format(del_i) +
                      "{:d} pixels in hor".format(del_j))

    if plotFlag:

        from matplotlib.patches import Rectangle
        plt.figure()
        plt.imshow(np.log10(intensity), cmap='inferno')

        plt.gca().add_patch(Rectangle((idxPeak_ij[1] - periodHor//2,
                                      idxPeak_ij[0] - periodVert//2),
                                      periodHor, periodVert,
                                      lw=2, ls='--', color='red',
                                      fill=None, alpha=1))

        plt.title('Selected Region ' + harmonic_ij[0] + harmonic_ij[1],
                  fontsize=18, weight='bold')
        plt.show()

    return imgFFT[idxPeak_ij[0] - periodVert//2:
                  idxPeak_ij[0] + periodVert//2,
                  idxPeak_ij[1] - periodHor//2:
                  idxPeak_ij[1] + periodHor//2]


def plot_harmonic_grid(img, harmonicPeriod=None, isFFT=False):

    """
    Takes the FFT of single 2D grating Talbot imaging and plot the grid from
    where we extract the harmonic in a image of the



    Parameters
    ----------
    img : 	ndarray – Data (data_exchange format)
        Experimental image, whith proper blank image, crop and rotation already
        applied.

    harmonicPeriod : integer or list of integers
        If list, it must be in the format ``[periodVert, periodHor]``. If
        integer, then [periodVert = periodHor``.
        ``periodVert`` and ``periodVert`` are the period of the harmonics in
        the reciprocal space in pixels. For the checked board grating,
        ``periodVert = sqrt(2) * pixel Size / grating Period * number of
        rows in the image``

    isFFT : Boolean
        Flag that tells if the input image ``img`` is in the reciprocal
        (``isFFT=True``) or in the real space (``isFFT=False``)

    """

    if not isFFT:
        imgFFT = np.fft.fftshift(np.fft.fft2(np.fft.fftshift(img), norm='ortho'))
    else:
        imgFFT = img

    (nRows, nColumns) = img.shape

    periodVert = harmonicPeriod[0]
    periodHor = harmonicPeriod[1]

    # adjusts for 1D grating
    if periodVert <= 0 or periodVert is None:
        periodVert = nRows

    if periodHor <= 0 or periodHor is None:
        periodHor = nColumns

    plt.figure()
    plt.imshow(np.log10(np.abs(imgFFT)), cmap='inferno')

    harV_min = -(nRows + 1) // 2 // periodVert
    harV_max = (nRows + 1) // 2 // periodVert

    harH_min = -(nColumns + 1) // 2 // periodHor
    harH_max = (nColumns + 1) // 2 // periodHor

    for harV in range(harV_min + 1, harV_max + 2):

        idxPeak_ij = _idxPeak_ij(harV, 0, nRows, nColumns,
                                 periodVert, periodHor)

        plt.axhline(idxPeak_ij[0] - periodVert//2, lw=2, color='r')

    for harH in range(harH_min + 1, harH_max + 2):

        idxPeak_ij = _idxPeak_ij(0, harH, nRows, nColumns,
                                 periodVert, periodHor)
        plt.axvline(idxPeak_ij[1] - periodHor // 2, lw=2, color='r')

    for harV in range(harV_min, harV_max + 1):
        for harH in range(harH_min, harH_max + 1):

            idxPeak_ij = _idxPeak_ij(harV, harH,
                                     nRows, nColumns,
                                     periodVert, periodHor)

            plt.plot(idxPeak_ij[1], idxPeak_ij[0],
                     'ko', mew=2, mfc="None", ms=15)

            plt.annotate('{:d}{:d}'.format(harV, harH),
                         (idxPeak_ij[1], idxPeak_ij[0]),
                         color='red', fontsize=20)

    plt.xlim(0, nColumns)
    plt.ylim(nRows, 0)
    plt.title('log scale FFT magnitude, Hamonics Subsets and Indexes',
              fontsize=16, weight='bold')


def plot_harmonic_peak(img, harmonicPeriod=None, isFFT=False, fname=None):
    """
    Funtion to plot the profile of the harmonic peaks ``10`` and ``01``.
    It is ploted 11 profiles of the 11 nearest vertical (horizontal)
    lines to the peak ``01`` (``10``)

    img : 	ndarray – Data (data_exchange format)
        Experimental image, whith proper blank image, crop and rotation already
        applied.

    harmonicPeriod : integer or list of integers
        If list, it must be in the format ``[periodVert, periodHor]``. If
        integer, then [periodVert = periodHor``.
        ``periodVert`` and ``periodVert`` are the period of the harmonics in
        the reciprocal space in pixels. For the checked board grating,
        ``periodVert = sqrt(2) * pixel Size / grating Period * number of
        rows in the image``

    isFFT : Boolean
        Flag that tells if the input image ``img`` is in the reciprocal
        (``isFFT=True``) or in the real space (``isFFT=False``)
    """


    if not isFFT:
        imgFFT = np.fft.fftshift(np.fft.fft2(np.fft.fftshift(img), norm='ortho'))
    else:
        imgFFT = img

    (nRows, nColumns) = img.shape

    periodVert = harmonicPeriod[0]
    periodHor = harmonicPeriod[1]


    # adjusts for 1D grating
    if periodVert <= 0 or periodVert is None:
        periodVert = nRows

    if periodHor <= 0 or periodHor is None:
        periodHor = nColumns

    fig = plt.figure(figsize=(10, 6))

    ax1 = fig.add_subplot(121)

    ax2 = fig.add_subplot(122)

    idxPeak_ij = _idxPeak_ij(0, 1,
                             nRows, nColumns,
                             periodVert, periodHor)

    for i in range(-5, 5):

        ax1.plot(np.abs(imgFFT[idxPeak_ij[0] - 100:idxPeak_ij[0] + 100,
                               idxPeak_ij[1]-i]),
                 lw=2, label='01 Vert ' + str(i))

    ax1.grid()

    idxPeak_ij = _idxPeak_ij(1, 0,
                             nRows, nColumns,
                             periodVert, periodHor)

    for i in range(-5, 5):

        ax2.plot(np.abs(imgFFT[idxPeak_ij[0]-i,
                               idxPeak_ij[1] - 100:idxPeak_ij[1] + 100]),
                 lw=2, label='10 Horz ' + str(i))

    ax2.grid()

    ax1.set_xlabel('Pixels')
    ax1.set_ylabel(r'$| FFT |$ ')

    ax2.set_xlabel('Pixels')
    ax2.set_ylabel(r'$| FFT |$ ')
    plt.show(block=False)

    if fname is not None:
        plt.savefig(fname)




def single_grating_harmonic_images(img, harmonicPeriod,
                                   searchRegion=10,
                                   plotFlag=False, verbose=False):

    """
    Auxiliary function to process the data of single 2D grating Talbot imaging.
    It obtain the (real space) harmonic images  00, 01 and 10.

    Parameters
    ----------
    img : 	ndarray – Data (data_exchange format)
        Experimental image, whith proper blank image, crop and rotation already
        applied.

    harmonicPeriod : list of integers in the format [periodVert, periodHor]
        ``periodVert`` and ``periodVert`` are the period of the harmonics in
        the reciprocal space in pixels. For the checked board grating,
        periodVert = sqrt(2) * pixel Size / grating Period * number of
        rows in the image. For 1D grating, set one of the values to negative or
        zero (it will set the period to number of rows or colunms).

    searchRegion: int
        search for the peak will be in a region of harmonicPeriod/searchRegion
        around the theoretical peak position. See also
        `:py:func:`wavepy.grating_interferometry.plot_harmonic_grid`

    plotFlag: boolean

    verbose: Boolean
        verbose flag.

    Returns
    -------
    three 2D ndarray data
        Images obtained from the harmonics 00, 01 and 10.

    """

    imgFFT = np.fft.fftshift(np.fft.fft2(img, norm='ortho'))

    if plotFlag:
        plot_harmonic_grid(imgFFT, harmonicPeriod=harmonicPeriod, isFFT=True)
        plt.show(block=False)

    imgFFT00 = extract_harmonic(imgFFT,
                                harmonicPeriod=harmonicPeriod,
                                harmonic_ij='00',
                                searchRegion=searchRegion,
                                isFFT=True,
                                plotFlag=plotFlag,
                                verbose=verbose)

    imgFFT01 = extract_harmonic(imgFFT,
                                harmonicPeriod=harmonicPeriod,
                                harmonic_ij=['0', '1'],
                                searchRegion=searchRegion,
                                isFFT=True,
                                plotFlag=plotFlag,
                                verbose=verbose)

    imgFFT10 = extract_harmonic(imgFFT,
                                harmonicPeriod=harmonicPeriod,
                                harmonic_ij=['1', '0'],
                                searchRegion=searchRegion,
                                isFFT=True,
                                plotFlag=plotFlag,
                                verbose=verbose)

    #  Plot Fourier image (intensity)
    if plotFlag:

        # Intensity is Fourier Space
        intFFT00 = np.log10(np.abs(imgFFT00))
        intFFT01 = np.log10(np.abs(imgFFT01))
        intFFT10 = np.log10(np.abs(imgFFT10))

        fig, axes = plt.subplots(nrows=1, ncols=3, figsize=(14, 4))

        for dat, ax, textTitle in zip([intFFT00, intFFT01, intFFT10],
                                      axes.flat,
                                      ['FFT 00', 'FFT 01', 'FFT 10']):

            # The vmin and vmax arguments specify the color limits
            im = ax.imshow(dat, cmap='inferno', vmin=np.min(intFFT00),
                           vmax=np.max(intFFT00))

            ax.set_title(textTitle)

        # Make an axis for the colorbar on the right side
        cax = fig.add_axes([0.92, 0.1, 0.03, 0.8])
        fig.colorbar(im, cax=cax)
        plt.suptitle('FFT subsets - Intensity', fontsize=18, weight='bold')
        plt.show(block=True)

    img00 = np.fft.ifft2(np.fft.ifftshift(imgFFT00), norm='ortho')

    # non existing harmonics will return NAN, so here we check NAN
    if np.all(np.isfinite(imgFFT01)):
        img01 = np.fft.ifft2(np.fft.ifftshift(imgFFT01), norm='ortho')
    else:
        img01 = imgFFT01

    if np.all(np.isfinite(imgFFT10)):
        img10 = np.fft.ifft2(np.fft.ifftshift(imgFFT10), norm='ortho')
    else:
        img10 = imgFFT10

    return (img00, img01, img10)


def single_2Dgrating_analyses(img, img_ref=None, harmonicPeriod=None,
                              unwrapFlag=1, plotFlag=True, verbose=False):

    """
    Function to process the data of single 2D grating Talbot imaging. It
    wraps other functions in order to make all the process transparent

    """

    # Obtain Harmonic images
    h_img = single_grating_harmonic_images(img, harmonicPeriod,
                                           plotFlag=plotFlag,
                                           verbose=verbose)

    if img_ref is not None:

        h_img_ref = single_grating_harmonic_images(img_ref, harmonicPeriod,
                                                   plotFlag=plotFlag,
                                                   verbose=verbose)
    else:
        h_img_ref = [None, None, None]
        h_img_ref[0] = np.exp(np.zeros((h_img[0].shape[0], h_img[0].shape[1])))
        h_img_ref[1] = h_img_ref[2] = h_img_ref[0]

    int00 = np.abs(h_img[0])/np.abs(h_img_ref[0])
    int01 = np.abs(h_img[1])/np.abs(h_img_ref[1])
    int10 = np.abs(h_img[2])/np.abs(h_img_ref[2])

    darkField01 = int01/int00
    darkField10 = int10/int00

    arg01 = np.angle(h_img[1]) - np.angle(h_img_ref[1])
    arg10 = np.angle(h_img[2]) - np.angle(h_img_ref[2])

    if unwrapFlag == 1:

        arg01 = unwrap_phase(arg01)
        arg10 = unwrap_phase(arg10)

    return [int00, int01, int10,
            darkField01, darkField10,
            arg01, arg10]




def visib_1st_harmonics(img, harmonicPeriod, searchRegion=20, verbose=False):
    """
    This function obtain the visibility in a grating imaging experiment by the
    ratio of the amplitudes of the first and zero harmonics. See
    https://doi.org/10.1364/OE.22.014041 .

    Note
    ----
    Note that the absolute visibility also depends on the higher harmonics, and
    for a absolute value of visibility all of them must be considered.


    Parameters
    ----------
    img : 	ndarray – Data (data_exchange format)
        Experimental image, whith proper blank image, crop and rotation already
        applied.

    harmonicPeriod : list of integers in the format [periodVert, periodHor]
        ``periodVert`` and ``periodVert`` are the period of the harmonics in
        the reciprocal space in pixels. For the checked board grating,
        periodVert = sqrt(2) * pixel Size / grating Period * number of
        rows in the image. For 1D grating, set one of the values to negative or
        zero (it will set the period to number of rows or colunms).

    searchRegion: int
        search for the peak will be in a region of harmonicPeriod/searchRegion
        around the theoretical peak position. See also
        `:py:func:`wavepy.grating_interferometry.plot_harmonic_grid`

    verbose: Boolean
        verbose flag.


    Returns
    -------
    (float, float)
        horizontal and vertical visibilities respectivelly from
        harmonics 01 and 10


    """

    imgFFT = np.fft.fftshift(np.fft.fft2(img, norm='ortho'))

    _idxPeak_ij_exp00 = _idxPeak_ij_exp(imgFFT, 0, 0,
                                        harmonicPeriod[0], harmonicPeriod[1],
                                        searchRegion)

    _idxPeak_ij_exp10 = _idxPeak_ij_exp(imgFFT, 1, 0,
                                        harmonicPeriod[0], harmonicPeriod[1],
                                        searchRegion)

    _idxPeak_ij_exp01 = _idxPeak_ij_exp(imgFFT, 0, 1,
                                        harmonicPeriod[0], harmonicPeriod[1],
                                        searchRegion)



    peak00 = np.abs(imgFFT[_idxPeak_ij_exp00[0], _idxPeak_ij_exp00[1]])
    peak10 = np.abs(imgFFT[_idxPeak_ij_exp10[0], _idxPeak_ij_exp10[1]])
    peak01 = np.abs(imgFFT[_idxPeak_ij_exp01[0], _idxPeak_ij_exp01[1]])

    return (2*peak10/peak00, 2*peak01/peak00)



