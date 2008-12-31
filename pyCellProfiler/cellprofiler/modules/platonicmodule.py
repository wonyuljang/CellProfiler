""" PlatonicModules.py - module to load images from files
"""

import os
import re

import PIL.Image
import numpy
import matplotlib.image

from cellprofiler import cpmodule, cpimage, preferences, variable

# strings for choice variables
MS_EXACT_MATCH = 'Text-Exact match'
MS_REGEXP = 'Text-Regular expressions'
MS_ORDER = 'Order'

FF_INDIVIDUAL_IMAGES = 'individual images'
FF_STK_MOVIES = 'stk movies'
FF_AVI_MOVIES = 'avi movies'
FF_OTHER_MOVIES = 'tif,tiff,flex movies'

DIR_DEFAULT_IMAGE = 'Default Image Directory'
DIR_DEFAULT_OUTPUT = 'Default Output Directory'
DIR_OTHER = 'Elsewhere...'

SB_GRAYSCALE = 'grayscale'
SB_BINARY = 'binary'

def default_cpimage_name(index):
    # the usual suspects
    names = ['DNA', 'Actin', 'Protein']
    if index < len(names):
        return names[index]
    return 'Channel%d'%(index+1)

class LoadImages(cpmodule.AbstractModule):
    """Load images from files.  This is the help text that will be displayed
       to the user.
    """
    def __init__(self):
        super(LoadImages, self).__init__()
        self.module_name = "LoadImages"
        
        # Settings
        self.file_types = variable.Choice('What type of files are you loading?',[FF_INDIVIDUAL_IMAGES, FF_STK_MOVIES, FF_AVI_MOVIES, FF_OTHER_MOVIES])
        self.match_method = variable.Choice('How do you want to load these files?', [MS_EXACT_MATCH, MS_REGEXP, MS_ORDER])
        self.match_exclude = variable.Text('If you want to exclude certain files, type the text that the excluded images have in common', variable.DO_NOT_USE)
        self.order_group_size = variable.Integer('How many images are there in each group?', 3)
        self.descend_subdirectories = variable.Binary('Analyze all subfolders within the selected folder?', False)
     
        # Settings for each CPimage
        self.images_common_text = [variable.Text('Type the text that these images have in common', 'DAPI')]
        self.images_order_position = [variable.Integer('What is the position of this image in each group', 1)]
        self.image_names = [variable.ImageNameProvider('What do you want to call this image in CellProfiler?', default_cpimage_name(0))]
        self.remove_images = [variable.DoSomething('Remove this image...','Remove', self.remove_imagecb, 0)]
        
        # Add another image
        self.add_image = variable.DoSomething('Add another image...','Add', self.add_imagecb)
        
        # Location settings
        self.location = variable.CustomChoice('Where are the images located?',
                                        [DIR_DEFAULT_IMAGE, DIR_DEFAULT_OUTPUT, DIR_OTHER])
        self.location_other = variable.DirectoryPath("Where are the images located?", '')

    def add_imagecb(self):
            'Adds another image to the variables'
            img_index = len(self.images_order_position)
            self.images_common_text += [variable.Text('Type the text that these images have in common', '')]
            self.images_order_position += [variable.Integer('What is the position of this image in each group', img_index+1)]
            self.image_names += [variable.ImageNameProvider('What do you want to call this image in CellProfiler?', default_cpimage_name(img_index))]
            self.remove_images += [variable.DoSomething('Remove this image...', 'Remove',self.remove_imagecb, img_index)]

    def remove_imagecb(self, index):
            'Remove an image from the variables'
            del self.images_common_text[index]
            del self.images_order_position[index]
            del self.image_names[index]
            del self.remove_images[index]

    def visible_variables(self):
        varlist = [self.file_types, self.match_method]
        if self.match_method == MS_EXACT_MATCH:
            varlist += [self.match_exclude]
        elif self.match_method == MS_ORDER:
            varlist += [self.order_group_size]
        varlist += [self.descend_subdirectories]
        
        # per image settings
        if self.match_method != MS_ORDER:
            for ctext, imname, rm in zip(self.images_common_text, self.image_names, self.remove_images):
                varlist += [ctext, imname, rm]
        else:
            for pos, imname, rm in zip(self.images_order_position, self.image_names, self.remove_images):
                varlist += [pos, imname, rm]
                
        varlist += [self.add_image]
        varlist += [self.location]
        if self.location == DIR_OTHER:
            varlist += [self.location_other]
        return varlist
        
    # Move this down somehere
    def directory_path(self):
        if self.location == 'Default image folder':
            return xxx_the_default_image_folder
        elif self.location == 'Default output filter':
            return xxx_the_default_output_folder
        else:
            return self.location_other

    def upgrade(self,variable_revision_number):
        """Rewrite the variables in the module to upgrade it to its
           current revision number
        """
        if variable_revision_number != self.variable_revision_number:
            raise NotImplementedError("Cannot read version %d of %s"%(
                variable_revision_number, self.module_name))
    
    variable_revision_number = 4
    
    def write_to_handles(self,handles):
        """Write out the module's state to the handles
        
        """
    
    def write_to_text(self,file):
        """Write the module's state, informally, to a text file
        """

    def prepare_run(self, pipeline, image_set_list):
        """Set up all of the image providers inside the image_set_list
        """
        if self.load_movies():
            raise NotImplementedError("Movies aren't implemented yet.")
        
        files = self.collect_files()
        if len(files) == 0:
            raise ValueError("there are no image files in the chosen directory (or subdirectories, if you requested them to be analyzed as well)")
        
        #Deal out the image filenames to a list of lists.
        image_names = self.image_name_vars()
        list_of_lists = [[] for x in image_names]
        for x in files:
            list_of_lists[x[1]].append(x[0])
        
        image_set_count = len(list_of_lists[0])
        for x,name in zip(list_of_lists[1:],image_names):
            if len(x) != image_set_count:
                raise RuntimeError("Image %s has %d files, but image %s has %d files"%(image_names[0],image_set_count,name.value,len(x)))
        list_of_lists = numpy.array(list_of_lists)
        root = self.image_directory()
        for i in range(0,image_set_count):
            image_set = image_set_list.get_image_set(i)
            providers = [LoadImagesImageProvider(name.value,root,file) for name,file in zip(image_names, list_of_lists[:,i])]
            image_set.providers.extend(providers)
        
    def run(self,pipeline,image_set,object_set,measurements, frame):
        """Run the module - add the measurements
        
        pipeline     - instance of CellProfiler.Pipeline for this run
        image_set    - the images in the image set being processed
        object_set   - the objects (labeled masks) in this image set
        measurements - the measurements for this run
        """
        for provider in image_set.providers:
            if isinstance(provider,LoadImagesImageProvider):
                filename = provider.get_filename()
                path = provider.get_pathname()
                name = provider.name
                measurements.add_measurement('Image','FileName_'+name, filename)
                measurements.add_measurement('Image','PathName_'+name, path)

    def get_categories(self,pipeline, object_name):
        """Return the categories of measurements that this module produces
        
        object_name - return measurements made on this object (or 'Image' for image measurements)
        """
        return ['Image']
      
    def get_measurements(self, pipeline, object_name, category):
        """Return the measurements that this module produces
        
        object_name - return measurements made on this object (or 'Image' for image measurements)
        category - return measurements made in this category
        """
        if object_name == 'Image':
            return ['FileName','PathName']
        return []
    
    def get_measurement_images(self,pipeline,object_name,category,measurement):
        """Return a list of image names used as a basis for a particular measure
        """
        return []
    
    def get_measurement_scales(self,pipeline,object_name,category,measurement,image_name):
        """Return a list of scales (eg for texture) at which a measurement was taken
        """
        return []
    
    def category(self):
        return "File Processing"

    
    def load_images(self):
        """Return true if we're loading images
        """
        return self.file_types == FF_INDIVIDUAL_IMAGES
    
    def load_movies(self):
        """Return true if we're loading movies
        """
        return self.file_types != FF_INDIVIDUAL_IMAGES
    
    def load_choice(self):
        """Return the way to match against files: MS_EXACT_MATCH, MS_REGULAR_EXPRESSIONS or MS_ORDER
        """
        return self.match_method.value
    
    def analyze_sub_dirs(self):
        """Return True if we should analyze subdirectories in addition to the root image directory
        """
        return self.descend_subdirectories.value
    
    def collect_files(self, dirs=[]):
        """Collect the files that match the filter criteria
        
        Collect the files that match the filter criteria, starting at the image directory
        and descending downward if AnalyzeSubDirs allows it.
        dirs - a list of subdirectories connecting the image directory to the
               directory currently being searched
        Returns a list of three-tuples where the first element of the tuple is the path
        from the root directory, including the file name, the second element is the
        index within the image variables (e.g. ImageNameVars).
        """
        path = reduce(os.path.join, dirs, self.image_directory() )
        files = os.listdir(path)
        files.sort()
        isdir = lambda x: os.path.isdir(os.path.join(path,x))
        isfile = lambda x: os.path.isfile(os.path.join(path,x))
        subdirs = filter(isdir, files)
        files = filter(isfile,files)
        path_to = (len(dirs) and reduce(os.path.join, dirs)) or ''
        files = [(os.path.join(path_to,file), self.filter_filename(file)) for file in files]
        files = filter(lambda x: x[1] != None,files)
        if self.analyze_sub_dirs():
            for dir in subdirs:
                files += self.collect_files(dirs + [dir])
        return files
        
    def image_directory(self):
        """Return the image directory
        """
        if self.location == DIR_DEFAULT_IMAGE:
            return preferences.get_default_image_directory()
        elif self.location == DIR_DEFAULT_OUTPUT:
            return preferences.get_default_output_directory()
        elif self.location_other.value[0] == '.':
            return os.path.join(preferences.get_default_image_directory(),self.location_other.value[1:])
        return self.location_other.value
    
    def image_name_vars(self):
        """Return the list of values in the image name field (the name that later modules see)
        """
        return self.image_names
        
    def text_to_find_vars(self):
        """Return the list of values in the image name field (the name that later modules see)
        """
        return self.images_common_text
    
    def text_to_exclude(self):
        """Return the text to match against the file name to exclude it from the set
        """
        return self.match_exclude
    
    def filter_filename(self, filename):
        """Returns either None or the index of the match variable
        """
        if self.text_to_exclude() != variable.DO_NOT_USE and \
            filename.find(self.text_to_exclude()) >=0:
            return None
        if self.load_choice() == MS_EXACT_MATCH:
            ttfs = self.text_to_find_vars()
            for i,ttf in zip(range(0,len(ttfs)),ttfs):
                if filename.find(ttf.value) >=0:
                    return i
        elif self.load_choice() == MS_REGULAR_EXPRESSIONS:
            ttfs = self.text_to_find_vars()
            for i,ttf in zip(range(0,len(ttfs)),ttfs):
                if re.search(ttf.value, filename):
                    return i
        else:
            raise NotImplementedError("Load by order not implemented")
        return None

class LoadImagesImageProvider(cpimage.AbstractImageProvider):
    """Provide an image by filename, loading the file as it is requested
    """
    def __init__(self,name,pathname,filename):
        self.__name = name
        self.__pathname = pathname
        self.__filename = filename
    
    def provide_image(self, image_set):
        """Load an image from a pathname
        """
        img = PIL.Image.open(self.get_full_name())
        img = matplotlib.image.pil_to_array(img)
        return cpimage.Image(img)
    
    def get_name(self):
        return self.__name
    
    def get_pathname(self):
        return self.__pathname
    
    def get_filename(self):
        return self.__filename
    
    def get_full_name(self):
        return os.path.join(self.get_pathname(),self.get_filename())
