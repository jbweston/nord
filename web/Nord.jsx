/*
 Copyright 2018 Joseph Weston

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/
import React from 'react' ;
import {SlideDown} from 'react-slidedown'
import Spinner from 'react-spinkit'
import {
  ComposableMap,
  ZoomableGroup,
  Geographies,
  Geography,
} from "react-simple-maps"

import 'bulma/css/bulma.css' ;
import 'react-slidedown/lib/slidedown.css'

// Import licence for GEOJSON so as to include it into the webpack output.
// This is necessary to avoid violating the license terms.
import './static/LICENSE'
import World from './static/world.geo.json'


const VPN = Object.freeze({
  disconnected:1,
  connecting:2,
  connected:3,
  disconnecting: 4,
}) ;

class Nord extends React.Component {

  constructor(props) {
    super(props) ;
    this.state = {
        enabled: false,
        loading: true,
        status: VPN.disconnected,
        country: null,
        host: null,
    } ;
    this.connection = null

    this.connect = this.connect.bind(this) ;
    this.disconnect = this.disconnect.bind(this) ;
    this.handleData = this.handleData.bind(this) ;
  }

  componentDidMount() {
    this.setState({enabled: false, loading: true})
    this.connection = new WebSocket('ws://127.0.0.1:5000/api') ;
    this.connection.onopen = () =>
      this.setState({enabled: true, loading: false}) ;
    this.connection.onerror = () =>
      this.setState({enabled: false, loading: false}) ;
    this.connection.onclose = () =>
      this.setState({enabled: false, loading: false}) ;
    this.connection.onmessage = this.handleData ;
  }

  handleData(msg) {
    msg = JSON.parse(msg.data)
    switch(msg.state) {
      case "connected":
        this.setState({status: VPN.connected, host: msg.host}) ;
        break ;
      case "disconnected":
        this.setState({status: VPN.disconnected}) ;
        break ;
    }
  }

  connect(geography) {
    const country_info = geography.properties ;
    this.setState({
        status: VPN.connecting,
        country: country_info.NAME,
        host: null,
    }) ;

    this.connection.send(JSON.stringify({
      method: 'connect',
      country: country_info.ISO_A2
    })) ;
  }

  disconnect() {
    this.setState((prev) => ({ ...prev, status: VPN.disconnecting })) ;

    this.connection.send(JSON.stringify({
      method: 'disconnect'
    })) ;
  }

  render() {
    return (
      <div>
        <Title/>
        <VPNStatus connection={ this.state }
                   onDisconnect={ this.disconnect }/>
        <WorldMap onClick={ this.connect }/>
      </div>
    ) ;
  }

}


const Title = () => (
  <section className="hero is-primary is-info has-text-centered">
      <div className="container">
        <div className="is-size-1">
          Nord
        </div>
      </div>
  </section>
) ;


const VPNStatus = (props) => {
  const connection = props.connection ;

  const ConnectionSpinner = () => (
    <div style={{"display": "inline-block", "margin-bottom": "-5px"}}>
      <Spinner name="double-bounce" />
    </div>
  ) ;

  const DisconnectButton = () => {
    var classes = "button is-danger " ;
    if (connection.status == VPN.disconnecting) {
      classes += "is-loading"
    }
    return (
      <button className={classes} onClick={ props.onDisconnect }>
        Disconnect
      </button>
    ) ;
  }

  const style = {"margin-right": "10px", display: "inline"} ;
  var color = "" ;
  var text = "" ;

  switch(props.connection.status) {
    case VPN.disconnected:
      break ;
    case VPN.connecting:
      color = "is-warning" ;
      text = <div>
              <div style={style}>
                Connecting to servers in {connection.country}
              </div>
              <ConnectionSpinner/>
            </div>
      break ;
    case VPN.connected:
    case VPN.disconnecting:
      color = "is-success" ;
      text = (<div>
                <div style={style}>
                  Connected to {connection.host}
                </div>
                <DisconnectButton/>
              </div>) ;
      break ;
  }

  if (!connection.enabled && !connection.loading) {
    color = "is-danger"
    text = <div style={style}>Lost connection to server</div>
  }

  const classes = "hero is-primary has-text-centered " + color

  return (
    <SlideDown>
      <section className={classes}>
          <div className="container">
            <div className="is-size-4">
              {text}
            </div>
          </div>
      </section>
    </SlideDown>
  ) ;
} ;


const WorldMap = (props) => {

  const zoom = 2 ;
  const center = [ 0, 30 ] ;
  const default_map_style = {
    fill: "#ECEFF1",
    stroke: "#607D8B",
    strokeWidth: 0.75,
    outline: "none",
  } ;
  const map_container_style = {
    width: "100%",
    height: "auto",
  } ;
  const map_style = {
    default: default_map_style,
    hover: { ...default_map_style, fill: "#CFD8DC" },
    pressed: { ...default_map_style, fill: "#CFD8DC" },
  } ;

  return (
    <ComposableMap style={ map_container_style }>
      <ZoomableGroup zoom={ zoom } center={ center }>
        <Geographies geography={ World }>
          {(geographies, projection) => geographies.map(geography => (
            <Geography
              key={ geography.id }
              geography={ geography }
              projection={ projection }
              style={ map_style }
              onClick={ props.onClick }
              />
          ))}
        </Geographies>
      </ZoomableGroup>
    </ComposableMap>
  ) ;
} ;


export default Nord ;
