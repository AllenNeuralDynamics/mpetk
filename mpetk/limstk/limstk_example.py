#!/usr/bin/env python

import src
from src import LIMStk as lims
import sys

def main(args):

    """
    This is an example of creating a trigger file and copying files for multi-patch.
    lims_scheduler_d.py should be running to receive requests from this library.

    When creating the session, HWBIgor and metadata are values you would be passing in (per confluence spec) rather than
    retrieving from lims2/ but 'id' will be the value you are passing to lims2/ to get the trigger directory and roi plans
    back from.

    These are defined in the lims_config.yml
    """

    # notice the "' notation when adding the filename - this is to allow the ' to appear in the trigger file
    # 'multipatch' is a lookup key for your specification but,
    # id, NWBIgor and metadata are key-value pairs you want to see in the trigger file but that do not come from lims
    # they are also defined in the limstk_config.
    lims_session = lims.Session('multipatch',  # defined in the limstk_config file
                                id=556516441,
                                NWBIgor="'/allen/programs/celltypes/production/incoming/mousecelltypes/neo;Ai14-316041.04.01_ephys_cell_cluster_1234.nwb'",
                                metadata="'/allen/programs/celltypes/production/incoming/mousecelltypes/Chat-IRES-Cre-neo;Ai14-316041.04.01_ephys_cell_cluster_1234.json'")


    # Because there could be multiple plans returned on this query, the user has to determine which plan id is correct
    # For these situations, there are 'manual' requests like specimens_by_id and specimens_by_well_name
    resp = lims_session.request('specimens_by_id', id=556516441)

    # This data can be manually added to the trigger data
    lims_session.trigger_data['id'] = resp['ephys_specimen_roi_plans'][0]['id']

    # enumerate the files you'd like to copy over
    lims_session.add_to_manifest('c:/Chat-IRES-Cre-neo;Ai14-316041.04.01_ephys_cell_cluster_1234.json')
    lims_session.add_to_manifest('c:/neo;Ai14-316041.04.01_ephys_cell_cluster_1234.nwb')

    # you could optionally copy a file over with a new name
    # lims_session.add_to_manifest('c:/myFile', dst_filename = 'newFilename') <--- no path necessary on dst_filename

    # to finish out, schedule the session
    lims_session.commit_manifest(trigger_file='Chat-IRES-Cre-neo;Ai14-316041.04.01_ephys_cell_cluster_1234.mp')

    # you can optionally schedule these transfer for a future date with the date_time keyword arg
    # date_time = datetime.datetime.now() + datetime.timedelta(seconds=3600)
    # would schedule the job for 1 hour in the future

if __name__ == '__main__':
    src.init_log()
    main(sys.argv)
