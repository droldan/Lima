from TacoCcd import *
from Lima import Frelon
from processlib import Tasks
import gc

DebParams.setTypeFlags(DebParams.AllFlags)
DebParams.setModuleFlags(DebParams.AllFlags)
DebParams.setFormatFlags(DebParams.AllFlags)

class FrelonTacoAcq(TacoCcdAcq):

    DEB_CLASS(DebModApplication, "FrelonTacoAcq")

    GetAcqFrames = 0x2
    
    StateDesc = {
        DEVFAULT:        'Fault: Camera off or disconnected',
        DevCcdReady:     'Ready: Camera is Idle',
        DevCcdAcquiring: 'Acquiring: Camera is Running',
    }
    
    @DEB_MEMBER_FUNCT
    def __init__(self, dev_name, dev_class=None, cmd_list=None):
        TacoCcdAcq.__init__(self, dev_name, dev_class, cmd_list)
        
        espia_dev_nb = 0
        self.m_acq = Frelon.FrelonAcq(espia_dev_nb)
        self.m_bpm_mgr  = Tasks.BpmManager()
        self.m_bpm_task = Tasks.BpmTask(self.m_bpm_mgr)
        self.m_get_acq_frames = False
        
    @DEB_MEMBER_FUNCT
    def __del__(self):
        pass

    @TACO_SERVER_FUNCT
    def reset(self):
        deb.Trace("Reseting the device!")
        ct = self.m_acq.getGlobalControl()
        ct.reset()

    @TACO_SERVER_FUNCT
    def getState(self):
        deb.Trace('Query device state ...')
        ct = self.m_acq.getGlobalControl()
        ct_status = ct.getStatus()
        acq_status = ct_status.AcquisitionStatus
        if acq_status == AcqRunning:
            self.state = DevCcdAcquiring
        elif acq_status == AcqReady:
            self.state = DevCcdReady
        else:
            msg = 'Acquisition error: %s' % (ct_status)
            end = index(msg, ', ImageCounters')
            msg = msg[:end] + '>'
            ct.resetStatus(True)
            ct.stopAcq()
            raise Exception, msg
        deb.Return('Device state: 0x%08x (%d)' % (self.state, self.state))
        return self.state

    @TACO_SERVER_FUNCT
    def getStatus(self):
        state = self.getState()
        dev_status = self.StateDesc[state]
        cam = self.m_acq.getFrelonCamera()
        ccd_status = cam.getStatus()
        status = '%s (CCD Status: 0x%02X)' % (dev_status, ccd_status)
        deb.Return('Dev status: %s' % status)
        return status

    @TACO_SERVER_FUNCT
    def getFrameDim(self, max_dim=False):
        ct_image = self.m_acq.getImageControl()
        if max_dim:
            max_size = ct_image.getMaxImageSize()
            fdim = FrameDim(max_size, ct_image.getImageType())
        else:
            fdim = ct_image.getImageDim()
        deb.Return('Frame dim: %s' % fdim)
        return fdim
    
    @TACO_SERVER_FUNCT
    def getType(self):
        cam = self.m_acq.getFrelonCamera()
        model = cam.getModel()
        type_nb = ((model.getAdcBits() == 16) and 2016) or 2014
        deb.Return('Getting type: %s' % type_nb)
        return type_nb

    @TACO_SERVER_FUNCT
    def getLstErrMsg(self):
        err_msg = ''
        deb.Return('Getting last err. msg: %s' % err_msg)
        return err_msg
    
    @TACO_SERVER_FUNCT
    def setTrigger(self, ext_trig):
        deb.Param('Setting trigger: %s' % ext_trig)
        ct_acq = self.m_acq.getAcqControl()
        exp_time = prev_exp_time = ct_acq.getAcqExpoTime()
        if ext_trig == 0:
            trig_mode = IntTrig
            if exp_time == 0:
                exp_time = 1
        elif ext_trig == 1:
            trig_mode = ((exp_time == 0) and ExtGate) or ExtTrigSingle
        elif ext_trig == 2:
            trig_mode = ExtTrigMult
        else:
            raise Exception, 'Invalid ext. trig: %s' % ext_trig
        ct_acq.setTriggerMode(trig_mode)
        if exp_time != prev_exp_time:
            ct_acq.setAcqExpoTime(exp_time)
    
    @TACO_SERVER_FUNCT
    def getTrigger(self):
        ct_acq = self.m_acq.getAcqControl()
        trig_mode = ct_acq.getTriggerMode()
        if trig_mode == IntTrig:
            ext_trig = 0
        elif trig_mode in [ExtTrigSingle, ExtGate]:
            ext_trig = 1
        elif trig_mode == ExtTrigMult:
            ext_trig = 2
        else:
            raise Exception, 'Invalid trigger mode: %s' % trig_mode
        deb.Return('Getting trigger: %s' % ext_trig)
        return ext_trig
    
    @TACO_SERVER_FUNCT
    def setNbFrames(self, nb_frames):
        deb.Param('Setting nb. frames: %s' % nb_frames)
        ct_acq = self.m_acq.getAcqControl()
        ct_acq.setAcqNbFrames(nb_frames)
    
    @TACO_SERVER_FUNCT
    def getNbFrames(self):
        ct_acq = self.m_acq.getAcqControl()
        nb_frames = ct_acq.getAcqNbFrames()
        deb.Return('Getting nb. frames: %s' % nb_frames)
        return nb_frames
    
    @TACO_SERVER_FUNCT
    def setExpTime(self, exp_time):
        deb.Param('Setting exp. time: %s' % exp_time)
        ct_acq = self.m_acq.getAcqControl()
        trig_mode = ct_acq.getTriggerMode()
        if exp_time == 0 and trig_mode == ExtTrigSingle:
            ct_acq.setTriggerMode(ExtGate)
        elif exp_time > 0 and trig_mode == ExtGate:
            ct_acq.setTriggerMode(ExtTrigSingle)
        ct_acq.setAcqExpoTime(exp_time)
    
    @TACO_SERVER_FUNCT
    def getExpTime(self):
        ct_acq = self.m_acq.getAcqControl()
        exp_time = ct_acq.getAcqExpoTime()
        deb.Return('Getting exp. time: %s' % exp_time)
        return exp_time

    @TACO_SERVER_FUNCT
    def setBin(self, bin):
        # SPEC format Y,X -> incompat. with getBin ...
        bin = Bin(bin[1], bin[0])
        deb.Param('Setting binning: %s' % bin)
        ct_image = self.m_acq.getImageControl()
        ct_image.setBin(bin)

    @TACO_SERVER_FUNCT
    def getBin(self):
        ct_image = self.m_acq.getImageControl()
        bin = ct_image.getBin()
        deb.Return('Getting binning: %s' % bin)
        return [bin.getX(), bin.getY()]

    @TACO_SERVER_FUNCT
    def getMaxRoi(self):
        ct_image = self.m_acq.getImageControl()
        max_roi_size = ct_image.getMaxImageSize()
        max_roi_size /= Point(ct_image.getBin())
        max_roi = Roi(Point(0, 0), max_roi_size)
        deb.Return('Max roi: %s' % max_roi)
        return max_roi
        
    @TACO_SERVER_FUNCT
    def setRoi(self, roi):
        roi = Roi(Point(roi[0], roi[1]), Point(roi[2], roi[3]))
        deb.Param('Setting roi: %s' % roi)
        if roi == self.getMaxRoi():
            roi = Roi()
        ct_image = self.m_acq.getImageControl()
        ct_image.setRoi(roi)

    @TACO_SERVER_FUNCT
    def getRoi(self):
        ct_image = self.m_acq.getImageControl()
        roi = ct_image.getRoi()
        if roi.isEmpty():
            roi = self.getMaxRoi()
        deb.Return('Getting roi: %s' % roi)
        tl = roi.getTopLeft()
        br = roi.getBottomRight()
        return [tl.x, tl.y, br.x, br.y]
            
    @TACO_SERVER_FUNCT
    def setFilePar(self, par_arr):
        deb.Param('Setting file pars: %s' % par_arr)
        ct_saving = self.m_acq.getSavingControl()
        pars = ct_saving.getParameters()
        pars.directory  = par_arr[0]
        pars.prefix     = par_arr[1]
        pars.suffix     = par_arr[2]
        pars.nextNumber = int(par_arr[3])
        index_format    = par_arr[4]
        if par_arr[5] in ['y', 'yes']:
            pars.overwritePolicy = CtSaving.Overwrite
        else:
            pars.overwritePolicy = CtSaving.Abort
        if pars.suffix.lower()[-4:] == '.edf':
            pars.fileFormat = CtSaving.EDF
        else:
            pars.fileFormat = CtSaving.RAW
        ct_saving.setParameters(pars)

    @TACO_SERVER_FUNCT
    def getFilePar(self):
        ct_saving = self.m_acq.getSavingControl()
        pars = ct_saving.getParameters()
        overwrite = (pars.overwritePolicy == CtSaving.Overwrite)
        over_str = (overwrite and 'yes') or 'no'
        index_format = '%04d'
        arr = [pars.directory, pars.prefix, pars.suffix, pars.nextNumber,
               index_format, over_str]
        par_arr = map(str, arr)
        deb.Return('File pars: %s' % par_arr)
        return par_arr

    @TACO_SERVER_FUNCT
    def setFileHeader(self, header_str):
        deb.Param('Setting file header: %s' % header_str)
        header_map = {}
        for line in header_str.split('\n'):
            token = line.split('=')
            key = token[0].strip()
            if not key:
                continue
            val = string.join(token[1:], '=').strip()
            if val[-1] == ';':
                val = val[:-1].strip()
            header_map[key] = val
        ct_saving = self.m_acq.getSavingControl()
        ct_saving.setCommonHeader(header_map)
        
    @TACO_SERVER_FUNCT
    def writeFile(self, frame_nb):
        deb.Param('Writing frame %s to file' % frame_nb)
        
    @TACO_SERVER_FUNCT
    def setChannel(self, input_chan):
        input_chan = Frelon.InputChan(input_chan)
        cam = self.m_acq.getFrelonCamera()
        ftm = cam.getFrameTransferMode()
        mode_name = cam.getInputChanModeName(ftm, input_chan)
        deb.Param('Setting input channel: %s [%s]' % (input_chan, mode_name))
        cam.setInputChan(input_chan)
    
    @TACO_SERVER_FUNCT
    def getChannel(self):
        cam = self.m_acq.getFrelonCamera()
        input_chan = cam.getInputChan()
        ftm = cam.getFrameTransferMode()
        mode_name = cam.getInputChanModeName(ftm, input_chan)
        deb.Return('Getting input channel: %s [%s]' % (input_chan, mode_name))
        return input_chan
        
    @TACO_SERVER_FUNCT
    def setMode(self, mode):
        deb.Param('Setting mode: %s (0x%x)' % (mode, mode))
        live_display = (mode & self.LiveDisplay) != 0
        self.setLiveDisplay(live_display)
        auto_save = (mode & self.AutoSave) != 0
        self.setAutosave(auto_save)
        self.m_get_acq_frames = (mode & self.GetAcqFrames) != 0
        
    @TACO_SERVER_FUNCT
    def getMode(self):
        mode = 0
        if self.getLiveDisplay():
            mode |= self.LiveDisplay
        if self.getAutosave():
            mode |= self.AutoSave
        if self.m_get_acq_frames:
            mode |= self.GetAcqFrames
        deb.Return('Getting mode: %s (0x%x)' % (mode, mode))
        return mode

    @TACO_SERVER_FUNCT
    def setHwPar(self, hw_par_str):
        hw_par = map(int, string.split(hw_par_str))
        deb.Param('Setting hw par: %s' % hw_par)
        kin_win_size, kin_line_beg, kin_stripes = self.getKinPars()
        flip_mode, kin_line_beg, kin_stripes, d0, roi_mode = hw_par
        cam = self.m_acq.getFrelonCamera()
        flip = Flip(flip_mode >> 1, flip_mode & 1)
        cam.setFlip(flip)
        roi_modes = [Frelon.None, Frelon.Slow, Frelon.Fast, Frelon.Kinetic]
        roi_modes_int = map(int, roi_modes)
        roi_mode = roi_modes[roi_modes_int.index(roi_mode)]
        cam.setRoiMode(roi_mode)
        if roi_mode == Frelon.Kinetic:
            self.setKinPars(kin_win_size, kin_line_beg, kin_stripes)
        else:
            deb.Warning("Ingoring Kinetic parameters")
        
    @TACO_SERVER_FUNCT
    def getHwPar(self):
        cam = self.m_acq.getFrelonCamera()
        flip = cam.getFlip()
        flip_mode = flip.x << 1 | flip.y
        roi_mode = cam.getRoiMode()
        kin_win_size, kin_line_beg, kin_stripes = self.getKinPars()
        hw_par = [flip_mode, kin_line_beg, kin_stripes, 0, roi_mode]
        deb.Return('Getting hw par: %s' % hw_par)
        hw_par_str = string.join(map(str, hw_par))
        return hw_par_str

    @TACO_SERVER_FUNCT
    def setKinPars(self, kin_win_size, kin_line_beg, kin_stripes):
        deb.Param('Setting kin pars: ' +
                  'kin_win_size=%s, kin_line_beg=%s, kin_stripes=%s' % \
                  (kin_win_size, kin_line_beg, kin_stripes))
        if kin_stripes > 1:
            deb.Warning('Ignoring kin_stripes=%d' % kin_stripes)
            
        ct_image = self.m_acq.getImageControl()
        bin = ct_image.getBin()
        if kin_win_size % bin.getY() != 0:
            msg = "Invalid kinetics window size (%d): " % kin_win_size + \
                  "must be multiple of vert. bin (%d)" % bin.getY()
            raise Exception, msg

        roi = ct_image.getRoi()
        if roi.isEmpty():
            roi = self.getMaxRoi()
        roi = roi.getUnbinned(bin)

        tl = Point(roi.getTopLeft().x, kin_line_beg)
        tl_aligned = Point(tl)
        tl_aligned.alignTo(Point(bin), Floor)
        size = Size(roi.getSize().getWidth(), kin_win_size)

        roi = Roi(tl_aligned, size)
        roi = roi.getBinned(bin)
        ct_image.setRoi(roi)
        
        roi_bin_offset  = tl
        roi_bin_offset -= tl_aligned

        cam = self.m_acq.getFrelonCamera()
        cam.setRoiBinOffset(roi_bin_offset)
        
    @TACO_SERVER_FUNCT
    def getKinPars(self):
        ct_image = self.m_acq.getImageControl()
        bin = ct_image.getBin()
        roi = ct_image.getRoi()
        if roi.isEmpty():
            roi = self.getMaxRoi()
        roi = roi.getUnbinned(bin)
        kin_win_size = roi.getSize().getHeight()
        cam = self.m_acq.getFrelonCamera()
        tl  = roi.getTopLeft()
        tl += cam.getRoiBinOffset()
        kin_line_beg = tl.y
        kin_stripes = 1
        deb.Return('Getting kin pars: ' +
                   'kin_win_size=%s, kin_line_beg=%s, kin_stripes=%s' % \
                   (kin_win_size, kin_line_beg, kin_stripes))
        return kin_win_size, kin_line_beg, kin_stripes

    
    @TACO_SERVER_FUNCT
    def setKinetics(self, kinetics):
        deb.Param('Setting the profile: %s' % kinetics)
        if kinetics == 0:
            ftm = Frelon.FFM
        elif kinetics == 3:
            ftm = Frelon.FTM
        else:
            raise Exception, 'Invalid kinetics value: %s' % kinetics
        cam = self.m_acq.getFrelonCamera()
        cam.setFrameTransferMode(ftm)
        
    @TACO_SERVER_FUNCT
    def getKinetics(self):
        cam = self.m_acq.getFrelonCamera()
        ftm = cam.getFrameTransferMode()
        if ftm == Frelon.FTM:
            kinetics = 3
        else:
            kinetics = 0
        deb.Return('Getting the profile: %s' % kinetics)
        return kinetics
    
    @TACO_SERVER_FUNCT
    def setKinWinSize(self, kin_win_size):
        deb.Param('Setting the kinetics window size: %s' % kin_win_size)
    
    @TACO_SERVER_FUNCT
    def getKinWinSize(self):
        kin_win_size = 0
        deb.Return('Getting the kinetics window size: %s' % kin_win_size)
        return kin_win_size
    
    @TACO_SERVER_FUNCT
    def startAcq(self):
        deb.Trace('Starting the device')
        ct = self.m_acq.getGlobalControl()
        ct.prepareAcq()
        ct.startAcq()
        
    @TACO_SERVER_FUNCT
    def stopAcq(self):
        deb.Trace('Stopping the device')
        ct = self.m_acq.getGlobalControl()
        ct.stopAcq()
    
    @TACO_SERVER_FUNCT
    def readFrame(self, frame_data):
        frame_nb, frame_size = frame_data
        deb.Param('frame_nb=%s, frame_size=%s' % (frame_nb, frame_size))
        frame_dim = self.getFrameDim()
        if frame_size != frame_dim.getMemSize():
            raise ValueError, ('Client expects %d bytes, frame has %d' % \
                               (frame_size, frame_dim.getMemSize()))
        ct = self.m_acq.getGlobalControl()
        img_data = ct.ReadImage(frame_nb)
        data = img_data.buffer
        s = data.tostring()
        if len(s) != frame_size:
            raise ValueError, ('Client expects %d bytes, data str has %d' % \
                               (frame_size, len(s)))
        return s

    @TACO_SERVER_FUNCT
    def startLive(self):
        deb.Trace('Starting live mode')
        self.setNbFrames(0)
        self.startAcq()
        
    @TACO_SERVER_FUNCT
    def setAutosave(self, autosave_act):
        deb.Param('Setting autosave active: %s' % autosave_act)
        if autosave_act:
            saving_mode = CtSaving.AutoFrame
        else:
            saving_mode = CtSaving.Manual
        ct_saving = self.m_acq.getSavingControl()
        ct_saving.setSavingMode(saving_mode)
    
    @TACO_SERVER_FUNCT
    def getAutosave(self):
        ct_saving = self.m_acq.getSavingControl()
        autosave_act = (ct_saving.getSavingMode() == CtSaving.AutoFrame)
        deb.Return('Getting autosave active: %s' % autosave_act)
        return autosave_act

    @TACO_SERVER_FUNCT
    def setLiveDisplay(self, livedisplay_act):
        deb.Param('Setting live display active: %s' % livedisplay_act)
        ct_display = self.m_acq.getDisplayControl()
        ct_display.setNames('_ccd_ds_', 'frelon_live')
        ct_display.setActive(livedisplay_act)
        
    @TACO_SERVER_FUNCT
    def getLiveDisplay(self):
        ct_display = self.m_acq.getDisplayControl()
        livedisplay_act = ct_display.isActive()
        deb.Return('Getting live display active: %s' % livedisplay_act)
        return livedisplay_act

    @TACO_SERVER_FUNCT
    def getCurrent(self):
        ct = self.m_acq.getGlobalControl()
        ct_status = ct.getStatus()
        img_counters = ct_status.ImageCounters
        if self.getAutosave() and not self.m_get_acq_frames:
            last_frame_nb = img_counters.LastImageSaved
        else:
            last_frame_nb = img_counters.LastImageAcquired
        nb_frames = last_frame_nb + 1
        deb.Return('Nb of frames: %s' % nb_frames)
        return nb_frames

    @TACO_SERVER_FUNCT
    def execCommand(self, cmd):
        deb.Param('Sending cmd: %s' % cmd)
        cam = self.m_acq.getFrelonCamera()
        ser_line = cam.getSerialLine()
        ser_line.write(cmd)
        resp = ser_line.readLine()
        deb.Return('Received response:')
        for line in resp.split('\r\n'):
            deb.Return(line)
        return resp

    @TACO_SERVER_FUNCT
    def getChanges(self):
        changes = 0
        deb.Trace('Getting changes: %s' % changes)
        return changes

    @TACO_SERVER_FUNCT
    def readCcdParams(self):
        exp_time = self.getExpTime()
        threshold = 0
        calib_intensity = -1
        max_frame_dim = self.getFrameDim(max_dim=True)
        roi = self.getRoi()
        is_live = -1

        ccd_params = [exp_time,
                      threshold,
                      calib_intensity,
                      max_frame_dim.getSize().getWidth(),
                      max_frame_dim.getSize().getHeight(),
                      roi[0], roi[1], roi[2], roi[3],
                      is_live]
        
        beam_params = self.readBeamParams()
        ccd_params += beam_params
        deb.Return('Getting CCD params: %s' % ccd_params)
        return ccd_params

    @TACO_SERVER_FUNCT
    def readBeamParams(self):
        frame_nb = -1
        ct = self.m_acq.getGlobalControl()
        img_data = ct.ReadImage(frame_nb)
        beam_params = self.calcBeamParams(img_data)
        deb.Return('Beam params: %s' % beam_params)
        return beam_params

    @TACO_SERVER_FUNCT
    def calcBeamParams(self, img_data):
        self.m_bpm_task.process(img_data)
        timeout = 1
        bpm_pars = self.m_bpm_mgr.getResult(timeout)
        if bpm_pars.errorCode != self.m_bpm_mgr.OK:
            raise Exception, ('Error calculating beam params: %d' %
                              bpm_pars.errorCode)
        
        nr_spots = 1
        auto_cal = -1
        exp_time = self.getExpTime()
        if exp_time > 0:
            norm_intensity = bpm_pars.beam_intensity / exp_time
        else:
            norm_intensity = 0

        beam_params = [nr_spots,
                       bpm_pars.beam_intensity,
                       bpm_pars.beam_center_x,
                       bpm_pars.beam_center_y,
                       bpm_pars.beam_fwhm_x,
                       bpm_pars.beam_fwhm_y,
                       bpm_pars.AOI_max_x - bpm_pars.AOI_min_x,
                       bpm_pars.AOI_max_y - bpm_pars.AOI_min_y,
                       bpm_pars.max_pixel_value,
                       bpm_pars.max_pixel_x,
                       bpm_pars.max_pixel_y,
                       bpm_pars.AOI_min_x,
                       bpm_pars.AOI_min_y,
                       bpm_pars.AOI_max_x,
                       bpm_pars.AOI_max_y,
                       bpm_pars.beam_center_x - bpm_pars.beam_fwhm_x / 2,
                       bpm_pars.beam_center_y - bpm_pars.beam_fwhm_y / 2,
                       bpm_pars.beam_center_x + bpm_pars.beam_fwhm_x / 2,
                       bpm_pars.beam_center_y + bpm_pars.beam_fwhm_y / 2,
                       norm_intensity,
                       auto_cal]
        deb.Return('Getting beam params: %s' % beam_params)
        return beam_params


class FrelonServer(CcdServer):

    DEB_CLASS(DebModApplication, "FrelonServer")
    
    @DEB_MEMBER_FUNCT
    def __init__(self, bin_name, pers_name):
        CcdServer.__init__(self, bin_name, pers_name)

        dev_name_list = self.getDevNameList()

        for dev_name in dev_name_list:
            dev = FrelonTacoAcq(dev_name)
            self.addDev(dev)

        self.startup()
        