# -*- coding: utf-8 -*-
"""
FigureData.py: Extract quantitative data from figures

This program allows one to extract quantitative numbers from published
figures that were not accompanied by tables with the data themselves.

Usage:

>>> import FigureData
>>> FigureData.go(input='Brammer11_Fig7.png',
                  output_file='myfigure.data')

The primary input is an image file of the figure (PNG, GIF, JPG). The
script prompts for the user to mark points on the figure defining the plot
regions. The steps are as follows:

1) Click two points on the x axis where you know the values from, e.g., the
   axis labels.  After clicking the points in the plot window, type the -x-
   values of those coordinates on the command line and hit <ENTER>.

2) Same as 1) for two points on the -y- axis.

3) Prompt to click on the lower-left and upper-right corners of the plot
   window

4) After 3) you can then click as many points as you want on the figure.
   To finish, click in the small border outside of the plot window to
   save the data to a file specified by the `output` keyword.

   The third column of the output file is a flag for marked data points
   that fall outside of the defined plot window.

MIT License

Copyright (c) 2016 Gabe Brammer

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.



Intern : div links

 http://prancer.physics.louisville.edu/astrowiki/index.php/Image_processing_with_Python_and_SciPy
https://gist.github.com/endolith/334196bac1cac45a4893
http://lukemiller.org/index.php/2011/06/digitizing-data-from-old-plots-using-digitize/
http://www.scipy-lectures.org/advanced/image_processing/

"""
import matplotlib.pyplot as plt
import matplotlib.image as mpimg

import numpy as np


class Globals(object):
    """Container for global variables accessible to the event handler."""

    def __init__(self):
        # Data read from clicks in the plot window
        self.xdata = []
        self.ydata = []

        # Plot range in axis coordinates
        self.xrange = None
        self.yrange = None

        # Pixel coordinates of axes marks
        self.xpix = None
        self.ypix = None

        # lower-left and upper-right coords of plot axes
        self.ll = None
        self.ur = None

        self.ax = None
        self.output_file = ''

G = Globals()


def onclick(event):
    """Event handler for clicks in the matplotlib plot window."""
    if event.xdata is None:
        # Click was outside the plot region
        # print 'Outside (%d, %d)' %(event.x, event.y)

        # Write the output file
        fp = open(G.output_file, 'w')
        for i in range(len(G.xdata)-6):
            xi, yi = G.xdata[i+6], G.ydata[i+6]
            xval, yval = translate_xy(xi, yi)
            inplot = ((xi >= G.ll[0]) & (xi <= G.ur[0]) &
                     (yi >= G.ll[1]) & (yi <= G.ur[1]))

            fp.write('%f %f %d\n' %(xval, yval, inplot*1))

        fp.close()
        print('Saved to %s.' %(G.output_file))

    else:
        # print('button=%d, x=%d, y=%d, xdata=%f,
        #       ydata=%f'%(event.button, event.x,
        #                  event.y, event.xdata, event.ydata))
        G.xdata.append(event.xdata)
        G.ydata.append(event.ydata)
        #
        if len(G.xdata) < 7:
            print('< mark >')

        if len(G.xdata) > 6:
            xval, yval = translate_xy(G.xdata[-1], G.ydata[-1])
            print('Mark [%f,%f]' %(xval, yval))
            G.ax.scatter(G.xdata[-1], G.ydata[-1], marker='o', color='white', s=40, alpha=0.7)
            G.ax.scatter(G.xdata[-1], G.ydata[-1], marker='o', color='red', s=20, alpha=0.7)
            plt.draw()

def translate_xy(x, y):
    """
    Translate the event (x,y) coordinates to plot coordinates
    """
    xval = (x-G.xpix[0])*np.diff(G.xrange)/np.diff(G.xpix)+G.xrange[0]
    yval = (y-G.ypix[0])*np.diff(G.yrange)/np.diff(G.ypix)+G.yrange[0]

    return xval, yval

def go(input=None, output_file='plot.data'):
    """
    Run the full script
    """

    # G is global container instantiated at import
    G.xdata = []
    G.ydata = []
    G.output_file = output_file

    # Display the plot
    try:
        im =mpimg.imread(input)
    except FileNotFoundError:
        raise
    else:
        fig = plt.figure()
        fig.subplots_adjust(left=0.02, bottom=0.02, right=1-0.02, top=1-0.02)

        ax = fig.add_subplot(111)
        G.ax = ax

        ax.imshow(im, aspect='auto', origin='upper')
        ax.set_xticks([0, im.size[0]])
        ax.set_yticks([0, im.size[1]])
        ax.set_xlim(0, im.size[0])
        ax.set_ylim(0, im.size[1])
        ax.set_xticklabels([])
        ax.set_yticklabels([])

        plt.draw()

        # Add "click" listener to the plot
        fig.canvas.mpl_connect('button_press_event', onclick)

        # Define -x- axis
        xticks = ''
        xticks = input('\n == Click two positions along the -x- axis and enter the tick coordinates here (e.g., 0,1): ')
        G.xrange = list(np.cast[float](xticks.split(',')))

        # Define -y- axis
        yticks = input('\n == Click two positions along the -y- axis and enter the tick coordinates here (e.g., 0,1): ')
        G.yrange = list(np.cast[float](yticks.split(',')))

        # Define the full plot window
        input(f"\n ==  Now mark the ll and ur corners of the plot axes."
              f"<Enter> when done.")

        G.xpix = G.xdata[0:2]
        G.ypix = G.ydata[2:4]
        G.ll = [G.xdata[4], G.ydata[4]]
        G.ur = [G.xdata[5], G.ydata[5]]
        xmin, ymin = translate_xy(G.ll[0], G.ll[1])
        xmax, ymax = translate_xy(G.ur[0], G.ur[1])
        print(f"\n Plot window:  x=[{xmin:f},{xmax:f}], "
              f"y=[{ymin:f},{ymax:f}] \n")

        print("\n == Now mark as many data points as you like."
              " == Click outside the plot window to save the `output_file`.")

        input('\n== <ENTER> when done.\n')
