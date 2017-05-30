import numpy as np
import scipy
import pylab as plt
import mypyutils as mylib
import myutils
import bovy_coords as bovyc
import gcutils 

#Footprint class definition
class Footprint:
    def __init__(self,lon,lat,name,Rhel=None,vrad=None,pmlon=None,pmlat=None,cootype='gal',degree=True,is_pml_star=True):
        
        self.deg=degree 
        self._f=np.pi/180.  
        self.name=name
        
        if 'gal' in cootype:
         self.l,self.b=lon,lat
         mm=bovyc.lb_to_radec(self.l,self.b,degree=self.deg)  
         if self.l.size>1: self.ra,self.dec=mm.T
         else: self.ra,self.dec=mm       
        else:
         self.ra,self.dec=lon,lat 
         mm=bovyc.radec_to_lb(self.ra,self.dec,degree=self.deg)
         if self.ra.size>1: self.l,self.b=mm.T 
         else: self.l,self.b=mm
            
        if Rhel is not None: self.Rhel=Rhel
        if vrad is not None: self.vrad=vrad
            
        if 'gal' in cootype:
            if pmlon is not None: 
                if is_pml_star: self.pmlstar,self.pml=pmlon,pmlon/np.cos(_f*self.b)
                else: self.pmlstar,self.pml=pmlon*np.cos(_f*self.b),pmlon
            if pmlat is not None: self.pmb=pmlat
        else:        
            if pmlon is not None: 
                if is_pml_star: self.pmrastar,self.pmra=pmlon,pmlon/np.cos(_f*self.dec)
                else: self.pmrastar,self.pmra=pmlon*np.cos(_f*self.dec),pmlon
            if pmlat is not None: self.pmdec=pmlat
         
        #Set center attributes
        self.compute_sky_center()
        
    def compute_sky_center(self):           
                
        #Need to get cartesian coords to do vector-average
        mm=bovyc.lbd_to_XYZ(self.l,self.b,np.ones_like(self.l),degree=True)
        if self.l.size>1: _xx,_yy,_zz=mm.T
        else: _xx,_yy,_zz=mm    
        _xc,_yc,_zc=_xx.sum(),_yy.sum(),_zz.sum()
        self.cl,self.cb=bovyc.XYZ_to_lbd(_xc,_yc,_zc,degree=True)[:2]
        self.cra,self.cdec=bovyc.lb_to_radec(self.cl,self.cb,degree=True)
        
    def mask_footprint(self,mask):
        
        #Apply mask to all array attributes of object
        for myattr in self.__dict__.keys():
        #If attribute is callable, proceed (only applicable to ndim>=1 arrays)
          if not callable(getattr(self,myattr)) and np.ndim(getattr(self,myattr))>=1:
            setattr(self,myattr,getattr(self,myattr)[mask])
            #print 'Attribute ',myattr, len(getattr(selfcopy,myattr))

#---------MW Streams class--------------------------------------------------------------------------------
        
class MWStreams(dict):
    
  #by pair of end-points------------------------------------------------------------------------------
  def init_by_end_points(self, gcstep=0.01,verbose=False):
    
      lib_end_points_filen='lib/lib_by_pair.dat'
        
      lono,lato,lonf,latf,ro,rf=scipy.genfromtxt(lib_end_points_filen,usecols=(3-1,4-1,5-1,6-1,8-1,9-1),unpack=True)
      name,sname,cootype=scipy.genfromtxt(lib_end_points_filen,usecols=(1-1,2-1,7-1),unpack=True,dtype='S')
  
      for i in range(len(lono)):
        #Get great-circle lons,lats given end-points 
        if verbose: print 'Reading pair-list for %s' % (name[i])        
        azs,lats,azcenter,latcenter=gcutils.get_gc_for_pair(lono[i],lato[i],lonf[i],latf[i],degree=True,step=gcstep) 
        
        #Do linear interpolation for the distance, not much better to do
        if ro[i]==rf[i]: D=ro[i]*np.ones_like(azs)
        elif rf[i]>ro[i]>0.: D=scipy.interp(azs,[lono[i],lonf[i]],[ro[i],rf[i]])    
        else: D=-1*np.ones_like(azs)
        
        #Create footprint appropriately depending on coord type, this will define the l,b,ra,dec attributes appropriately
        footprint=Footprint(azs,lats,name[i],Rhel=D,degree=True,cootype=cootype[i])
        
        #Store
        self[name[i]]=footprint     
    
  #--------------by pole----------------------------------------------------------
  def init_by_poles(self,gcstep=0.1,verbose=False):  
        lib_poles_filen='lib/lib_by_pole.dat'

        name,pole_coot,c_coot=scipy.genfromtxt(lib_poles_filen,usecols=(0,3,6),unpack=True,dtype='S')
        pole_dat=scipy.genfromtxt(lib_poles_filen,usecols=(1,2,4,5,7,8,9,10),filling_values=-999.)
        pole_lons,pole_lats,clons,clats,dlons,dlats,ros,rfs=pole_dat.T

        for i in np.arange(len(pole_lons)):
           #Convert central coords to the same as pole coords for consistency
           if verbose: print 'Reading pole-list for %s' % (name[i])        
 
           #If center coords are given, make sure they're in the same system as pole coords
           if (clons[i]!=-999. and clats[i]!=-999.):     
             if  c_coot[i] in pole_coot[i]:
                center=[clons[i],clats[i]]   #If in the same system, just save
                if verbose: print ' same system, center:',center
             else:
               if 'gal' in c_coot[i]: clons[i],clats[i]=bovyc.lb_to_radec(clons[i],clats[i],degree=True) 
               else: clons[i],clats[i]=bovyc.radec_to_lb(clons[i],clats[i],degree=True)
               center=[clons[i],clats[i]]    
               if verbose: print ' computed center',center                     
           else: 
             center=None                          
                                  
           if dlons[i]<-90: dlons[i]=None
           if dlats[i]<0.: dlats[i]=0.                 
                                                       
           #Get realization of great-circle, given stream's orbital pole [and optionally center,length and width]
           gc_lons,gc_lats=gcutils.get_gc_for_pole(pole_lons[i],pole_lats[i],degree=True,center=center,
                                                    dlon=dlons[i],dlat=dlats[i],step=gcstep)
                            
           #Do linear interpolation for the distance, not much better to do
           if ros[i]==rfs[i]: D=ros[i]*np.ones_like(gc_lons)
           elif rfs[i]>ros[i]>0.: D=scipy.interp(gc_lons,[lono[i],lonf[i]],[ros[i],rfs[i]])    
           else: D=-1*np.ones_like(gc_lons)
                                           
           #Create footprint appropriately depending on coord type, this will define the l,b,ra,dec attributes appropriately
           footprint=Footprint(gc_lons,gc_lats,name[i],Rhel=D,degree=True,cootype=pole_coot[i])
        
           #Store
           self[name[i]]=footprint     

  #-----------------by lonlat range--------------------------------------------------------------
  def init_by_lonlat_range(self,Nran=1000,verbose=False,Rstat='mean'):
                
    lib_llrange_filen='lib/lib_by_lonlat_range.dat'
    
    #Validate options for Rstat
    stat_types = ['min', 'max', 'mean', 'median']
    if Rstat not in stat_types:
        raise ValueError("Invalid stat type. Expected one of: %s" % stat_types)
    Rstat_func=getattr(np,Rstat)

    
    name,cootype=scipy.genfromtxt(lib_llrange_filen,usecols=(0,7),unpack=True,dtype='S')
    azo_l,azf_l,lato_l,latf_l,ro_l,rf_l,stype=scipy.genfromtxt(lib_llrange_filen,usecols=(1,2,3,4,5,6,8),unpack=True,
                                                               filling_values=-999.)

    ind=np.arange(azo_l.size)

    for i in ind:
     #Parse corners
     if verbose: print 'Reading lon-lat range for %s' % (name[i])        
     azo,azf,lato,latf,ro,rf=azo_l[i],azf_l[i],lato_l[i],latf_l[i],ro_l[i],rf_l[i]

     #Random realization of coords    
     Rs,azs,lats=mylib.get_random_spherical_coords(Nran,rad=[ro,rf],az=[azo,azf],lat=[lato,latf],degree=True)

     #Create footprint appropriately depending on coord type, this will define the l,b,ra,dec attributes appropriately
     footprint=Footprint(azs,lats,name[i],Rhel=Rstat_func(Rs)*np.ones_like(Rs),degree=True,cootype=cootype[i])
        
     #Store
     self[name[i]]=footprint  
        

  #-----------------------by list of stars-------------------------------------------------------
  def init_by_star_list(self,verbose=False,Nint=300):
            
     lib_by_stars_list_filen='lib/lib_by_star.log'  
            
     list_dat=scipy.genfromtxt(lib_by_stars_list_filen,usecols=(1-1,2-1,3-1,4-1,5-1,6-1))
     list_sdat=scipy.genfromtxt(lib_by_stars_list_filen,usecols=(7-1,8-1,9-1),dtype='S')       
        
     #Deal with one-liners   
     if np.ndim(list_dat)==1: 
       list_dat,list_sdat=np.reshape(list_dat,(1,list_dat.size)),np.reshape(list_sdat,(1,list_sdat.size))
            
     #Parse       
     lon_col,lat_col,Rhel_col,interp_flg,progtype_col,cntflg_col=list_dat.astype(int).T      
     #Convert col numbers to python-style
     lon_col,lat_col,Rhel_col,progtype_col,cntflg_col=lon_col-1,lat_col-1,Rhel_col-1,progtype_col-1,cntflg_col-1       
     cootype,name,fname=list_sdat.T    

     #Loop over library of star list files
     for i in range(list_dat[:,0].size):
       
       if verbose: print 'Reading star list for %s' % (name[i])
       azs,lats,Rhels,cntflg=scipy.genfromtxt('lib/'+fname[i],usecols=(lon_col[i],lat_col[i],Rhel_col[i],cntflg_col[i]),
                                              unpack=True) 
       
       if interp_flg[i]==1 and azs.size>1:
         #connect these with linear interpolation  
         az_int=np.linspace(azs.min(),azs.max(),Nint)
         lat_int =scipy.interp(az_int,azs,lats)
         Rhel_int=scipy.interp(az_int,azs,Rhels)
       else:
        az_int,lat_int,Rhel_int=azs,lats,Rhels          
                          
       #Create footprint appropriately depending on coord type, this will define the l,b,ra,dec attributes appropriately
       footprint=Footprint(az_int,lat_int,name[i],Rhel=Rhel_int,degree=True,cootype=cootype[i])
                        
       #If cntflg_col==1, force center to this coords (instead of the default vector mean)
       if cntflg_col[i]>=0:
        if (cntflg==1).sum()>1: print 'Warning, more than one point flaged as center in %s, choosing first one.' % (fname[i]) 
        caz,clat=azs[cntflg==1][0],lats[cntflg==1][0]    
        auxfoot=Footprint(caz,clat,'dummy',degree=True,cootype=cootype[i]) 
        footprint.cra,footprint.cdec=auxfoot.cra,auxfoot.cdec
        footprint.cl,footprint.cb=auxfoot.cl,auxfoot.cb
        
       #Store
       self[name[i]]=footprint              
        
  def __init__(self,verbose=True,gcstep=0.1,N=1000,Rstat='mean'):
        
    #A MWStreams object is a dictionary in which each entry is a Footprint object, indexed by each stream's name.
    #Since everyone likes to define a stream in a different way, there are several contructor methods to create the stream's
    #footprints, depending on what data is available in the literature
      
    #Initialize empty dictionary
    dict.__init__(self) 
    
    #---For streams defined by RA-DEC or l-b range, create and append footprints
    self.init_by_lonlat_range(verbose=verbose,Nran=N,Rstat=Rstat) 
    
    #---For streams defined by their end-points, create and append footprints
    self.init_by_end_points(verbose=verbose,gcstep=gcstep)
    
    #---For streams defined by their poles, create and append footprints
    self.init_by_poles(verbose=verbose,gcstep=gcstep)   
         
    #---For streams defined by an explicit list of stars, create and append footprints    
    self.init_by_star_list(verbose=verbose)
    
  #-------------method to plot whole MW streams compilation object at once------------------------------------
  def plot_stream_compilation(self,ax,Rstat='mean',Rrange=[0.,9e9],plot_stream_type='all',plot_names=True,plot_colorbar=False,
                              scat_kwargs=None,text_kwargs=None,sym_kwargs=None,cb_kwargs=None,cootype='gal',verbose=False,
                              exclude_streams=[]): 

   #Validate options for cootype
   coo_types = ['gal', 'equ']
   if cootype not in coo_types:
        raise ValueError("Invalid coo type. Expected one of: %s" % coo_types)
        
   #Validate options for Rstat
   stat_types = ['min', 'max', 'mean', 'median']
   if Rstat not in stat_types:
        raise ValueError("Invalid stat type. Expected one of: %s" % stat_types)
   Rstat_func=getattr(np,Rstat)

   #Validate options for stream types to be plotted
   stream_types = ['all', 'gc', 'dwarf']
   if plot_stream_type not in stream_types:
        raise ValueError("Invalid stream type. Expected one of: %s" % stream_types)

   #Set a few plotting and labelling defaults  
   Rmax=0.
   for i in self.keys(): Rmax=np.max([Rmax,np.max(self[i].Rhel)]) 
   scatter_kwargs=dict(marker='o',s=8.,edgecolor='none',vmin=0.,vmax=Rmax,alpha=0.5)
   textlab_kwargs=dict(horizontalalignment='center',verticalalignment='bottom',zorder=99)
   textsym_kwargs=dict(marker='+',color='k',ms=5,zorder=textlab_kwargs['zorder'])
   colorbar_kwargs=dict(extend='max')

   #but override whichever are user-supplied (doing it this way I ensure using my own defaults and not matplotlib's
   #if user supplies values for some (but not all) keywords
   if scat_kwargs is not None:
        for key in scat_kwargs.keys(): scatter_kwargs[key]=scat_kwargs[key]
   if text_kwargs is not None:
        for key in text_kwargs.keys(): textlab_kwargs[key]=text_kwargs[key]
   if sym_kwargs is not None:
        for key in sym_kwargs.keys(): textsym_kwargs[key]=sym_kwargs[key]
   if cb_kwargs is not None:
        for key in cb_kwargs.keys(): colorbar_kwargs[key]=cb_kwargs[key]       

   #If Rrange is supplied, use it to set vmax 
   if Rrange[1]<9e9: scatter_kwargs['vmax']=Rrange[1]

   #------------------------------PLOT---------------------------------------------------------------------- 
   for i in self.keys(): 
        
    ro,rf=np.min(self[i].Rhel),np.max(self[i].Rhel)    
    if 'gal' in cootype: lons,latts,loncenter,latcenter=self[i].l,self[i].b,self[i].cl,self[i].cb
    else: lons,latts,loncenter,latcenter=self[i].ra,self[i].dec,self[i].cra,self[i].cdec      
    
    #Skip if stream does not have any part overlapping Rrange
    if (ro>0) and not (ro<=Rrange[1] and rf>=Rrange[0]):
      if verbose: 
        print 'Skipping %s [%.1f,%.1f], outside selected Rrange [%.1f,%.1f]' % (self[i].name,ro,rf,Rrange[0],Rrange[1])
      continue
      
    if i in exclude_streams:
        print 'Skipping excluded stream: %s' % (self[i].name)
        continue

    cc=ax.scatter(lons,latts,c=self[i].Rhel,**scatter_kwargs)
    if plot_names:
     ax.plot(loncenter,latcenter,**textsym_kwargs)
     ax.text(loncenter,latcenter,self[i].name,**textlab_kwargs)
     
    if cc and plot_colorbar: 
        cbar=plt.colorbar(cc,ax=ax,**colorbar_kwargs)
        cbar.solids.set_rasterized(True)
        cbar.solids.set_edgecolor("face")
        plot_colorbar=False
  


def plot_globular_clusters(ax,plot_colorbar=False,scat_kwargs=None,galactic=True):
    
 #Harris's Globular cluster compilation
 gc_l,gc_b,gc_Rhel=scipy.genfromtxt('/Users/cmateu/trabajo/local_group/globular_clusters_compilations/globular_cluster_params.harris.tableI.csv',
                              missing_values="",usecols=(5-1,6-1,7-1),unpack=True,delimiter=',',dtype=np.float)
 gc_RA,gc_DEC=bovyc.lb_to_radec(gc_l,gc_b,degree=True).T

 #set a few plotting and labelling defaults  
 scatter_kwargs=dict(marker='x',s=70.,vmin=0.,zorder=0) 
 #but override whichever are user-supplied (doing it this way I ensure using my own defaults and not matplotlib's
 #if user supplies values for some (but not all) keywords
 if scat_kwargs is not None: 
    for key in scat_kwargs.keys(): scatter_kwargs[key]=scat_kwargs[key]  

 #Plot globular cluster layer       
 if galactic: cc=ax.scatter(gc_l,gc_b,c=gc_Rhel,**scatter_kwargs)           
 else: cc=ax.scatter(gc_RA,gc_DEC,c=gc_Rhel,**scatter_kwargs)
        
 if plot_colorbar: plt.colorbar(cc,ax=ax)                
       
#------------------------------------------